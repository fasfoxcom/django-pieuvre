import logging
import typing
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.conf import settings
from pieuvre import Workflow as PieuvreWorkflow
from pieuvre.exceptions import (
    TransitionAmbiguous,
    TransitionUnavailable,
    CircularWorkflowError,
)

from djpieuvre.constants import (
    ON_TASK_ASSIGN_GROUP_HOOK,
    ON_TASK_ASSIGN_USER_HOOK,
    TASK_STATES,
    WORKFLOW_PERM_SUFFIX_WRITE,
    WORKFLOW_PERM_PREFIX,
)
from djpieuvre.exceptions import WorkflowDoesNotExist
from djpieuvre.mixins import WorkflowEnabled
from djpieuvre.models import PieuvreProcess, PieuvreTask
from djpieuvre.utils import get_app_name, camel_to_snake

logger = logging.getLogger(__name__)
_workflows = defaultdict(dict)


class Workflow(PieuvreWorkflow):
    """
    A persisted workflow with an associated PieuvreProcess model.
    """

    # Set to True to persist the workflow to the DB
    persist = False
    # If persist is True, the target model must be set to facilitate introspection
    target_model = None
    # If initial_state is defined, it is used to instantiate the process.
    # Otherwise, first element of the states list is used.
    initial_state = None
    # Workflow versions can coexist.
    # To implement this, the `name` property should be overridden so that different workflow versions share
    # the same name.
    version = 1
    extra_enabled_hooks_and_checks = (
        ON_TASK_ASSIGN_GROUP_HOOK,
        ON_TASK_ASSIGN_USER_HOOK,
    )
    fancy_name = None

    def __init_subclass__(cls, **kwargs):
        """
        Register the workflow so that it can be easily instantiated
        """
        super().__init_subclass__(**kwargs)
        register(cls)

    def __init__(self, model, initial_state=None):
        # Behavior is only different if the model is persisted
        if self.persist:
            # This is because the process model itself saves the state, not the target model,
            # and Django-Pieuvre uses a precise field for that
            if self.state_field_name != PieuvreProcess.STATE_FIELD_NAME:
                raise ValueError("State field must not be set on a persisted workflow")

            # If the target model is not persisted, then we cannot create a PieuvreProcess instance in database
            # FIXME: we could only save the PieuvreProcess later on
            if not model.pk:
                raise ValueError("model must be persisted before workflow is called")

            # Do some magic: if provided model is a PieuvreProcess, fetch the target model,
            # otherwise create or fetch the process assigned to that model
            if isinstance(model, PieuvreProcess):
                self.process_target = model.process_target
            else:
                self.process_target = model
                model = None

                states = getattr(self, "states", None)

                if not states:
                    # States must be defined because we need to instantiate the PieuvreProcess with an initial state
                    raise ValueError("States must be defined on the workflow")

                if not initial_state:
                    # Assume states are given in order
                    initial_state = self.get_initial_state()

                # Override model with the PieuvreProcess
                # FIXME: we should not save the object here so that it is only saved if the workflow advances

                # First let's try to see if the process has been prefetched
                if hasattr(self.process_target, "processes"):
                    processes = [
                        p
                        for p in getattr(self.process_target, "processes")
                        if p.workflow_name == self.__class__.name
                    ]
                    if processes:
                        model = processes[0]

                if model is None:
                    kwargs = {
                        "content_type": ContentType.objects.get_for_model(
                            self.process_target
                        ),
                        "object_id": self.process_target.pk,
                        "workflow_name": self.__class__.name,
                    }

                    try:
                        # when get_or_create is executed in concurrent call, an integrity error would be raised to
                        # alert about an integrity violation
                        # a PieuvreProcess has an uniqueness constraint on (content_type, object_id, workflow_name)
                        kwargs["defaults"] = {
                            PieuvreProcess.STATE_FIELD_NAME: initial_state,
                            "workflow_version": getattr(self, "version", 1),
                        }
                        model, _ = PieuvreProcess.objects.get_or_create(**kwargs)
                    except IntegrityError as e:
                        model = PieuvreProcess.objects.get(**kwargs)

        super().__init__(model)

    def _advance_workflow(self, transition=None):

        transition = transition or self._get_next_transition()
        # If `auto_advance` is True it means that the transition, despite being manual, should not create a task
        # and can be auto advanced. This is useful for transitions that must not be triggered automatically
        # but should not be automatically assigned to users
        manual_transition = transition.get("manual", False)
        create_task = transition.get("create_task", True)

        if manual_transition and create_task:
            # Manual transition: we must not advance the workflow, only create a task
            source_state = transition["source"]

            if hasattr(self.states, "for_value"):
                # If states are django extended choices, then use it
                source_state_name = self.states.for_value(source_state).display
            else:
                source_state_name = source_state

            with transaction.atomic():
                # We need a lock to avoid concurrency issues
                obj = PieuvreProcess.objects.select_for_update().get(pk=self.model.pk)
                task, _ = PieuvreTask.objects.get_or_create(
                    process=self.model,
                    task=source_state,
                    state=TASK_STATES.CREATED,
                    defaults={"name": source_state_name},
                )

            # Check if the workflow gives us insights about whom to assign
            groups, users = [], []
            assign_group = self._on_task_assign_group_hook.get(transition["name"])
            if assign_group:
                for func in assign_group:
                    groups.extend(func(tuple(transition.items())))
            assign_user = self._on_task_assign_user_hook.get(transition["name"])
            if assign_user:
                for func in assign_user:
                    users.extend(func(tuple(transition.items())))

            if not users and not groups:
                # Fallback to default assignment
                assign_group = getattr(self, "default_group", None)
                if assign_group:
                    groups = assign_group()
                assign_user = getattr(self, "default_user", None)
                if assign_user:
                    users = assign_user()

            task.assign(transition, users=users, groups=groups)
        elif not manual_transition:
            # No need for run_transition because this comes from _get_next_transition()
            getattr(self, transition["name"])()
        # Else, the transition is manual but does not create a task, so we do nothing

    def advance_workflow(self):
        """
        Advance the workflow if the transition is automatic, or create a manual task if the
        transition is meant to be manual.
        If the transition is manual, the task must be completed for the workflow to advance.
        """

        can_advance = True
        seen_transitions = set()

        while can_advance:
            # if the current transition is manual, we can advance only once
            try:
                next_transition = self._get_next_transition()
            except TransitionUnavailable as e:
                can_advance = False
            else:
                is_next_manual = next_transition.get("manual", False)
                self._advance_workflow(next_transition)
                can_advance = not is_next_manual

                if can_advance and next_transition["name"] in seen_transitions:
                    # Avoid infinite loop and abort
                    raise CircularWorkflowError()

                seen_transitions.add(next_transition["name"])

    def get_authorized_transitions(
        self,
        state: typing.Optional[str] = None,
        user: typing.Optional[settings.AUTH_USER_MODEL] = None,
    ):
        return self._get_authorized_transitions(state, user)

    def _get_authorized_transitions(
        self,
        state: typing.Optional[str] = None,
        user: typing.Optional[settings.AUTH_USER_MODEL] = None,
    ):
        available_transitions = self.get_available_transitions(state, False)

        if not user:
            return available_transitions

        authorized_transitions = []
        user_groups = user.groups.all()

        for trans in available_transitions:
            if not trans.get("manual", False):
                authorized_transitions.append(trans)
                continue

            assign_group = self._on_task_assign_group_hook.get(trans["name"], [])
            assign_user = self._on_task_assign_user_hook.get(trans["name"], [])
            authorized_groups = []
            authorized_users = []

            for func in assign_group:
                authorized_groups.extend(func(tuple(trans.items())))

            for func in assign_user:
                authorized_users.extend(func(tuple(trans.items())))

            if user in authorized_users or set(user_groups).intersection(
                authorized_groups
            ):
                authorized_transitions.append(trans)

        return authorized_transitions

    @classmethod
    def applies_to(cls, instance):
        """
        This method takes an instance as parameter and returns a boolean
        if the workflow applies to this instance.
        This allows filtering out some workflows depending on the instance.
        """
        return True

    def is_allowed(self, user, perm=WORKFLOW_PERM_SUFFIX_WRITE):
        """
        Return True if the user or its group can access the workflow instance.
        """
        # Workflow without a target_model is allowed by default because it is not
        # related to a given instance (which might require some permissions).
        if (
            not (app_name := get_app_name(self.target_model))
            or not user
            or user.is_superuser
        ):
            return True

        perm = f"{WORKFLOW_PERM_PREFIX}_{camel_to_snake(self.perm_name)}_{perm}"

        # Permissions are not mandatory: if it does not exist, assume the user
        # is allowed to access the workflow.
        if not self._is_permission_defined(perm):
            return True

        return user.has_perm(f"{app_name}.{perm}")

    def _is_permission_defined(self, current_perm):
        """
        Return True if the permission exists.
        """
        return any(
            perm[0] == current_perm for perm in self.process_target._meta.permissions
        )

    def _get_next_transition(self):
        """
        Return the next transition that can be reached.
        The workflow must be unambiguous (a single transition must be possible).
        """
        state = self._get_model_state()
        transitions = self.get_available_transitions(state, return_all=False)
        if len(transitions) > 1 and self._check_manual_transitions(transitions):
            return transitions[0]

        return super()._get_next_transition()

    def _check_manual_transitions(self, transitions):
        """
        Check whether all next transitions are manual
        """
        return all(transition.get("manual", False) for transition in transitions)

    @classmethod
    @property
    def name(cls):
        """
        Return a name uniquely identifying this workflow.
        """
        # Class name is imperfect (as you could define workflows named identically
        # in separate folders), so be cautious.
        return cls.__name__

    @classmethod
    @property
    def perm_name(cls):
        """
        Return a name identifying this workflow permissions. It does not need to be unique.
        """
        # Class name is imperfect (as you could define workflows named identically
        # in separate folders), so be cautious.
        return cls.name


def register(cls: typing.Type[Workflow]):
    """
    Register the workflow class, which is required to easily instantiate workflows
    from PieuvreProcess instances.
    """
    name = cls.name
    version = getattr(cls, "version", 1)
    if name in _workflows and version in _workflows[name]:
        # This is probably an error, but leave it to the developer to decide
        logger.warning(f"Duplicated workflow {name} version {version}")

    _workflows[name][version] = cls

    if hasattr(cls, "target_model"):
        # Also register the workflow on the model itself so that it can be easily found later on
        # This is especially useful to return all available workflows on a specific object
        if not issubclass(cls.target_model, WorkflowEnabled):
            raise AttributeError(
                "Target model must inherit from djpieuvre.WorkflowEnabled"
            )
        cls.target_model.register_workflow(cls)


def get(workflow_name: str, workflow_version: int):
    """
    Given its name and version, returns a registered workflow, or None if it does not exist.
    """
    return _workflows.get(workflow_name).get(workflow_version)

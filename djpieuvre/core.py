import logging
import typing
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from pieuvre import Workflow as PieuvreWorkflow
from pieuvre.core import BaseDecorator

from djpieuvre.constants import ON_TASK_ASSIGN_GROUP_HOOK, ON_TASK_ASSIGN_USER_HOOK
from djpieuvre.mixins import WorkflowEnabled
from djpieuvre.models import PieuvreProcess, PieuvreTask

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

                states = getattr(self, "states", None)
                if not initial_state and not states:
                    # States must be defined because we need to instantiate the PieuvreProcess with an initial state
                    raise ValueError("States must be defined on the workflow")
                elif not initial_state:
                    # Assume states are given in order
                    initial_state = getattr(self, "initial_state", None) or states[0]

                # Override model with the PieuvreProcess
                # FIXME: we should not save the object here so that it is only saved if the workflow advances
                model, _ = PieuvreProcess.objects.get_or_create(
                    content_type=ContentType.objects.get_for_model(model),
                    object_id=model.pk,
                    workflow_name=self.__class__.name,
                    defaults={
                        PieuvreProcess.STATE_FIELD_NAME: initial_state,
                        "workflow_version": getattr(self, "version", 1),
                    },
                )

        super().__init__(model)

    def advance_workflow(self):
        """
        Advance the workflow if the transition is automatic, or create a manual task if the
        transition is meant to be manual.
        If the transition is manual, the task must be completed for the workflow to advance.
        """
        transition = self._get_next_transition()
        if transition.get("manual", False):
            # Manual transition: we must not advance the workflow, only create a task
            # TODO: access rights
            task, _ = PieuvreTask.objects.get_or_create(
                process=self.model, task=transition["name"]
            )

            # Check if the workflow gives us insights about whom to assign
            groups, users = [], []
            assign_group = self._on_task_assign_group_hook.get(transition["name"])
            if assign_group:
                for func in assign_group:
                    groups.extend(func(task, transition))
            assign_user = self._on_task_assign_user_hook.get(transition["name"])
            if assign_user:
                for func in assign_user:
                    users.extend(func(task, transition))

            if not users and not groups:
                # Fallback to default assignment
                assign_group = getattr(self, "default_group", None)
                if assign_group:
                    groups = assign_group(task)
                assign_user = getattr(self, "default_user", None)
                if assign_user:
                    users = assign_user(task)

            task.assign(transition, users=users, groups=groups)
        else:
            getattr(self, transition["name"])()

    @classmethod
    @property
    def name(cls):
        """
        Return a name uniquely identifying this workflow
        """
        return cls.__name__


def register(cls: typing.Type[Workflow]):
    """
    Register the workflow class, which is required to easily instantiate workflows from PieuvreProcess instances.
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
    Given its name and version, return a registered workflow, or None if it does not exist.
    """
    return _workflows.get(workflow_name).get(workflow_version)

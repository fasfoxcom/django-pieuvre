import logging
import typing

from django.contrib.contenttypes.models import ContentType
from pieuvre import Workflow as PieuvreWorkflow, WorkflowEnabled

from djpieuvre.models import PieuvreProcess, PieuvreTask

logger = logging.getLogger(__name__)
_workflows = {}


class Workflow(PieuvreWorkflow):
    persist = False

    def __init_subclass__(cls, **kwargs):
        """
        Register the workflow so that it can be easily instantiated
        """
        super().__init_subclass__(**kwargs)
        register(cls)

    def __init__(self, model, default_state=None):
        if self.persist:
            if self.state_field_name != PieuvreProcess.STATE_FIELD_NAME:
                raise ValueError("State field must not be set on a persisted workflow")

            if not model.pk:
                raise ValueError("model must be persisted before workflow is called")

            # Do some magic: if provided model is a process, fetch the target model,
            # otherwise create or fetch the process assigned to that model
            if isinstance(model, PieuvreProcess):
                self.process_target = model.process_target
            else:
                self.process_target = model
                # That could fail if states are
                states = getattr(self, "states", None)
                if not default_state and not states:
                    raise ValueError("States must be defined on the workflow")
                elif not default_state:
                    default_state = states[0]
                # Override model with the PieuvreProcess
                # FIXME: maybe we should not save the object here so that it is only saved if the workflow advances
                model, _ = PieuvreProcess.objects.get_or_create(
                    content_type=ContentType.objects.get_for_model(model),
                    object_id=model.pk,
                    workflow_name=_get_workflow_name(self.__class__),
                    defaults={PieuvreProcess.STATE_FIELD_NAME: default_state},
                )

        super().__init__(model)

    def advance_workflow(self):
        """
        Advance the workflow if the transition is automatic, or create a manual task if the
        transition is meant to be manual.
        """
        transition = self._get_next_transition()
        if transition.get("manual", False):
            # Manual transition: we must not advance the workflow, only create a task
            # TODO: access rights
            task, _ = PieuvreTask.objects.get_or_create(
                process=self.model, task=transition["name"]
            )
            task.assign(transition)
        else:
            getattr(self, transition["name"])()


def _get_workflow_name(cls: typing.Type[Workflow]):
    return cls.__name__


def register(cls: typing.Type[Workflow]):
    name = _get_workflow_name(cls)
    if name in _workflows:
        logger.warning(f"Duplicated workflow {name}")
    _workflows[name] = cls


def get(workflow_name: str):
    return _workflows.get(workflow_name)

from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from extended_choices import Choices
from rest_framework import serializers

from djpieuvre import constants
from djpieuvre.constants import TASK_STATES
from djpieuvre.exceptions import WorkflowDoesNotExist
from djpieuvre.models import PieuvreTask, PieuvreProcess
from djpieuvre.mixins import RequestInfoMixin, WorkflowEnabled
from pieuvre.exceptions import (
    TransitionDoesNotExist,
    InvalidTransition,
    TransitionUnavailable,
    TransitionAmbiguous,
)


class WorkflowSerializer(serializers.Serializer):
    # we expose the model pk as the workflow pk
    pk = serializers.CharField(source="model.pk")
    fancy_name = serializers.CharField()
    name = serializers.CharField()
    state = serializers.CharField()
    transitions = serializers.SerializerMethodField()
    states = serializers.SerializerMethodField()

    def get_transitions(self, workflow):
        return workflow.get_authorized_transitions(user=self.context.get("user", None))

    def get_states(self, workflow):
        if not isinstance(workflow.states, Choices):
            return workflow.states

        return {
            key: workflow.states.for_value(key).display
            for key in workflow.states.values.keys()
        }


class WorkflowStateSerializer(serializers.Serializer):
    # we expose the model pk as the workflow pk
    pk = serializers.CharField(source="model.pk")
    fancy_name = serializers.CharField()
    name = serializers.CharField()
    state = serializers.CharField()


class InstanceWorkflowSerializer(serializers.Serializer, RequestInfoMixin):
    """
    This is a model serializer but since the target model is not known, we make it a generic serializer.
    Target model must inherit from WorkflowEnabled mixin.
    """

    workflows = serializers.SerializerMethodField()
    workflow_states = serializers.SerializerMethodField()

    def get_workflow_serializer_class(self):
        return WorkflowSerializer

    def get_workflow_states_serializer_class(self):
        return WorkflowStateSerializer

    def _get_workflows(self, obj):
        # We only need the read permission to list the workflows
        return [
            w
            for w in obj.workflow_instances
            if w.is_allowed(self.user, perm=constants.WORKFLOW_PERM_SUFFIX_READ)
        ]

    @extend_schema_field(serializers.ListSerializer(child=WorkflowSerializer()))
    def get_workflows(self, obj):
        return self.get_workflow_serializer_class()(
            self._get_workflows(obj),
            many=True,
            read_only=True,
            context={"user": self.user},
        ).data

    @extend_schema_field(serializers.ListSerializer(child=WorkflowStateSerializer()))
    def get_workflow_states(self, obj):
        return self.get_workflow_states_serializer_class()(
            self._get_workflows(obj), many=True, read_only=True
        ).data


class PieuvreTaskListSerializer(serializers.ModelSerializer):
    process_id = serializers.CharField()
    model = serializers.CharField(source="process.content_type.model")
    model_id = serializers.CharField(source="process.object_id")
    process_name = serializers.CharField(source="process.workflow_name")
    process_fancy_name = serializers.CharField(source="process.workflow_fancy_name")
    instance_repr = serializers.SerializerMethodField()

    @staticmethod
    def get_instance_repr(task):
        try:
            return task.process.process_target.task_repr()
        except AttributeError:
            return None

    class Meta:
        model = PieuvreTask
        read_only_fields = [
            "id",
            "process_id",
            "process_name",
            "process_fancy_name",
            "model",
            "model_id",
            "instance_repr",
            "state",
            "name",
            "task",
            "created_at",
        ]

        fields = read_only_fields + []


class PieuvreTaskDetailSerializer(PieuvreTaskListSerializer):
    transitions = serializers.SerializerMethodField()

    def get_transitions(self, task):
        request = self.context.get("request", None)
        user = request.user if request else None
        return task.process.workflow.get_authorized_transitions(user=user)

    class Meta(PieuvreTaskListSerializer.Meta):
        fields = [f for f in PieuvreTaskListSerializer.Meta.fields] + [
            "transitions",
            "data",
        ]


class PieuvreTaskCompleteSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
    transition = serializers.CharField(
        write_only=True,
        required=True,
        help_text="The name of the transition to execute",
    )

    def save(self, **kwargs):
        transition = self.validated_data["transition"]

        if self.instance.state != TASK_STATES.CREATED:
            raise serializers.ValidationError("Task was already processed")

        # we can't mark a task as done unless
        # the workflow state changes.
        with transaction.atomic():
            try:
                if self.instance.data is None:
                    self.instance.data = {}
                self.instance.data["reason"] = self.validated_data.get("reason")
                self.instance.complete(transition)
                self.instance.save()
            except (
                TransitionDoesNotExist,
                InvalidTransition,
                TransitionUnavailable,
                TransitionAmbiguous,
            ) as we:
                raise serializers.ValidationError(we.message)


class AdvanceWorkflowSerializer(serializers.Serializer):
    workflow = serializers.PrimaryKeyRelatedField(
        queryset=PieuvreProcess.objects.all(), required=True
    )
    transition = serializers.CharField(
        write_only=True,
        required=False,
        help_text="Optional: the name of the transition to execute",
    )

    @staticmethod
    def _get_workflow(pieuvre_process: PieuvreProcess, obj: WorkflowEnabled):
        # FIXME: improve this logic
        target_workflows = list(
            filter(
                lambda w: pieuvre_process.pk == w.model.pk,
                obj.workflow_instances,
            )
        )

        if not target_workflows or len(target_workflows) > 1:
            # not normal, there are many instances of the same (workflow, pieuvre_process)
            raise WorkflowDoesNotExist("Workflow does not exist")

        return target_workflows[0]

    def validate(self, data):
        data = super().validate(data)
        try:
            data["workflow"] = self._get_workflow(data["workflow"], self.context["obj"])
        except WorkflowDoesNotExist:
            raise serializers.ValidationError({"workflow": "Workflow does not exist"})

        transition_name = data.get("transition")
        # Make sure the transition exists and can be executed by the current user
        transition = next(
            (
                t
                for t in data["workflow"].get_authorized_transitions(
                    user=self.context.get("user")
                )
                if t["name"] == transition_name
            ),
            None,
        )
        if transition_name and (not transition or transition.get("create_task", True)):
            # If create_task is True, the transition must be activated by completing the task, not by the
            # advance workflow endpoint.
            raise serializers.ValidationError(
                {"transition": "Transition is not available"}
            )
        return data

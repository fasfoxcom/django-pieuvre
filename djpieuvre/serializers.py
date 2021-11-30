from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from djpieuvre.models import PieuvreTask, PieuvreProcess
from djpieuvre.mixins import RequestInfoMixin
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

    def get_transitions(self, workflow):
        return workflow.get_authorized_transitions(user=self.context.get("user", None))


class InstanceWorkflowSerializer(serializers.Serializer, RequestInfoMixin):
    """
    This is a model serializer but since the target model is not known, we make it a generic serializer.
    Target model must inherit from WorkflowEnabled mixin.
    """

    workflows = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListSerializer(child=WorkflowSerializer()))
    def get_workflows(self, obj):
        workflows = [w for w in obj.workflow_instances if w.is_allowed(self.user)]
        return WorkflowSerializer(
            workflows, many=True, read_only=True, context={"user": self.user}
        ).data


class PieuvreTaskListSerializer(serializers.ModelSerializer):
    process_name = serializers.CharField(source="process.workflow_name")
    process_fancy_name = serializers.CharField(source="process.workflow_fancy_name")

    class Meta:
        model = PieuvreTask
        fields = [
            "id",
            "process_id",
            "process_name",
            "process_fancy_name",
            "state",
            "name",
            "task",
        ]


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
        help_text="The name of the transition to be " "executed",
    )

    def save(self, **kwargs):
        transition = self.validated_data["transition"]

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

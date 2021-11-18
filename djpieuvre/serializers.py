from rest_framework import serializers

from djpieuvre.models import PieuvreTask
from djpieuvre.mixins import RequestInfoMixin


class WorkflowSerializer(serializers.Serializer):
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

    def get_workflows(self, obj):
        workflows = [w for w in obj.workflow_instances if w.is_allowed(self.user)]
        return WorkflowSerializer(
            workflows, many=True, read_only=True, context={"user": self.user}
        ).data


class PieuvreTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieuvreTask
        fields = ["process_id", "state", "name", "task"]

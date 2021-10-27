from rest_framework import serializers

from djpieuvre.models import PieuvreTask


class WorkflowSerializer(serializers.Serializer):
    name = serializers.CharField()
    state = serializers.CharField()
    transitions = serializers.SerializerMethodField()

    def get_transitions(self, workflow):
        return workflow.get_available_transitions()


class InstanceWorkflowSerializer(serializers.Serializer):
    """
    This is a model serializer but since the target model is not know, we make it a generic serializer.
    Target model must inherit from WorkflowEnabled mixin.
    """

    workflows = WorkflowSerializer(
        many=True, read_only=True, source="workflow_instances"
    )


class PieuvreTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieuvreTask
        fields = ["process_id", "state", "name", "task"]

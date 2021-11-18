from rest_framework.decorators import action
from rest_framework.response import Response

from djpieuvre.serializers import InstanceWorkflowSerializer


class WorkflowModelMixin:
    @action(detail=True, methods=["get"])
    def workflows(self, request, pk=None):
        """
        Return workflows applicable to current object
        """
        instance = self.get_object()
        serializer = InstanceWorkflowSerializer(instance, context={"request": request})
        return Response(serializer.data)

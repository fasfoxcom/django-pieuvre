from django.shortcuts import render
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from djpieuvre.models import PieuvreTask
from djpieuvre.serializers import PieuvreTaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    Viewset to handle tasks
    """

    queryset = PieuvreTask.objects.all()
    serializer_class = PieuvreTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        task = self.get_object()
        task.complete()
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)

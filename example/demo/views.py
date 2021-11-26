from rest_framework import viewsets

from djpieuvre.drf_mixins import WorkflowModelMixin, AdvanceWorkflowMixin
from .models import MyProcess
from .serializers import MyProcessSerializer


class MyProcessViewSet(WorkflowModelMixin, AdvanceWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = MyProcessSerializer
    queryset = MyProcess.objects.all()

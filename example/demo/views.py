from rest_framework import viewsets

from djpieuvre.drf_mixins import WorkflowModelMixin
from .models import MyProcess
from .serializers import MyProcessSerializer


class MyProcessViewSet(WorkflowModelMixin, viewsets.ModelViewSet):
    serializer_class = MyProcessSerializer
    queryset = MyProcess.objects.all()

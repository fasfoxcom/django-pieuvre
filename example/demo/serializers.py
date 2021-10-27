from rest_framework import serializers

from djpieuvre.serializers import InstanceWorkflowSerializer
from .models import MyProcess


class MyProcessSerializer(InstanceWorkflowSerializer, serializers.ModelSerializer):
    class Meta:
        model = MyProcess
        fields = ["my_property", "workflows"]

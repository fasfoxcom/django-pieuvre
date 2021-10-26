from rest_framework import serializers

from djpieuvre.models import PieuvreTask


class PieuvreTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieuvreTask
        fields = ["process_id", "state", "name", "task"]

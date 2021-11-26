from drf_spectacular.utils import extend_schema
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from pieuvre.exceptions import (
    TransitionDoesNotExist,
    InvalidTransition,
    TransitionUnavailable,
    TransitionAmbiguous,
)
from rest_framework import mixins, viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from djpieuvre import utils
from djpieuvre.constants import TASK_STATES
from djpieuvre.models import PieuvreTask
from djpieuvre.serializers import (
    PieuvreTaskListSerializer,
    PieuvreTaskDetailSerializer,
    PieuvreTaskCompleteSerializer,
)
from djpieuvre import utils
from django.db import transaction


class TaskFilterSet(filters.FilterSet):
    status = filters.ChoiceFilter(
        field_name="state", label="Status", choices=TASK_STATES
    )

    class Meta:
        model = PieuvreTask
        fields = ["status"]


class TaskViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Viewset to handle tasks
    """

    queryset = PieuvreTask.objects.all()
    serializer_class = PieuvreTaskListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = TaskFilterSet

    def get_serializer_class(self):
        if self.action in (
                "retrieve",
                "complete"
        ):
            return PieuvreTaskDetailSerializer
        return self.serializer_class

    def get_queryset(self):
        """
        Return the queryset of tasks the authenticated user is allowed to access
        """
        qs = super().get_queryset()
        user = self.request.user

        f = utils.get_task_predicate(user)
        return qs.filter(f)

    @extend_schema(request=PieuvreTaskCompleteSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):

        deserializer = PieuvreTaskCompleteSerializer(data=request.data)
        if not deserializer.is_valid():
            raise serializers.ValidationError(deserializer.errors)

        task = self.get_object()

        transition = deserializer.validated_data["transition"]

        # we can't mark a task as done unless
        # the workflow state changes.
        with transaction.atomic():
            try:
                task.complete(transition)
                task.save()
            except (
                    TransitionDoesNotExist,
                    InvalidTransition,
                    TransitionUnavailable,
                    TransitionAmbiguous,
            ) as we:
                raise serializers.ValidationError(we.message)

        serializer = self.get_serializer(task)

        return Response(serializer.data)

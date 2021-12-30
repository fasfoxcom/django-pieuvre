from collections import defaultdict

from django.db.models import QuerySet, prefetch_related_objects
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets, permissions
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

    queryset = PieuvreTask.objects.select_related("process__content_type").all()
    serializer_class = PieuvreTaskListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = TaskFilterSet

    def get_serializer_class(self):
        if self.action in ("retrieve", "complete"):
            return PieuvreTaskDetailSerializer
        return self.serializer_class

    def get_serializer(self, *args, **kwargs):
        # If multiple objects are passed to this method, enrich them
        if kwargs.get("many"):
            args = [self.prefetch_related_objects(args[0]), *args[1:]]
        return super().get_serializer(*args, **kwargs)

    @staticmethod
    def prefetch_related_objects(objs):
        """
        This is a hack to prefetch the tasks process target instances. Since there are multiple
        target models, we cannot use `prefetch_related`.
        We could directly use prefetch_related_objects but then we could not prefetch some specific fields
        for each model, so we need to group the objects by target model, then use `prefetch_related_objects`.
        """
        if isinstance(objs, QuerySet):
            # Materialize the queryset so that we only deal with lists
            objs = list(objs)

        # Group all PieuvreTasks by content type
        objs_by_type = defaultdict(list)
        for obj in objs:
            objs_by_type[obj.process.content_type_id].append(obj)

        # Now prefetch the data we need
        lookup_prefix = "process__process_target"
        for content_type, content_type_objs in objs_by_type.items():
            # There is at least one element of this type so the following is safe
            model_class = content_type_objs[0].process.content_type.model_class()
            # From that we can get the fields we need to prefetch in order to optimize even more
            if hasattr(model_class, "task_repr") and hasattr(
                model_class.task_repr, "select_related"
            ):
                lookups = [
                    f"{lookup_prefix}__{field}"
                    for field in model_class.task_repr.select_related
                ]
                lookups.append(lookup_prefix)
            else:
                lookups = [lookup_prefix]
            prefetch_related_objects(content_type_objs, *lookups)

        return objs

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

        task = self.get_object()

        deserializer = PieuvreTaskCompleteSerializer(instance=task, data=request.data)
        deserializer.is_valid(raise_exception=True)

        deserializer.save()
        serializer = self.get_serializer(task)

        return Response(serializer.data)

from django.db.models import Q
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

    def get_queryset(self):
        """
        Return the queryset of tasks the authenticated user is allowed to access
        """
        qs = super().get_queryset()
        user = self.request.user
        # User is always defined in our case, thanks to the IsAuthenticated permission, but this allows
        # a superclass to remove the need for auth
        # First filter: the task is not assigned at all. Might apply to unauthenticated users
        f = Q(users__isnull=True) & Q(groups__isnull=True)
        if user:
            f = (
                f
                | Q(users=user)  # Or current user is assigned
                | Q(  # Or current user belongs to a group that is assigned
                    groups__in=user.groups.all()
                )
            )
        return qs.filter(f)

    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        task = self.get_object()
        task.complete()
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)

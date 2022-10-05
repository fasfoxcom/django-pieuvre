from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from djpieuvre import constants
from djpieuvre.mixins import WorkflowEnabled
from djpieuvre.models import PieuvreProcess
from djpieuvre.serializers import InstanceWorkflowSerializer
from djpieuvre.serializers import WorkflowSerializer, AdvanceWorkflowSerializer


class WorkflowModelMixin:
    @action(detail=True, methods=["get"])
    def workflows(self, request, pk=None):
        """
        Return workflows applicable to current object
        """
        instance = self.get_object()
        serializer = InstanceWorkflowSerializer(instance, context={"request": request})
        return Response(serializer.data)


class WorkflowDoesNotExist(Exception):
    pass


class AdvanceWorkflowMixin(object):
    """
    The aim of this mixin is to expose an endpoint that should help the frontend to advance a workflow (only from its
    initial state to the next), starting from its PieuvreProcess.
    This implementation only cares about the first state.
    """

    @extend_schema(
        request=AdvanceWorkflowSerializer,
        responses=WorkflowSerializer,
    )
    @action(
        detail=True,
        url_path=r"ops/advance_workflow",
        methods=["post"],
        serializer_class=AdvanceWorkflowSerializer,
    )
    def advance_workflow(self, request, *args, **kwargs):
        obj = self.get_object()

        serializer = AdvanceWorkflowSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        try:
            workflow = self._get_workflow(
                serializer.validated_data.get("workflow"), obj
            )
        except WorkflowDoesNotExist as e:
            return HttpResponseBadRequest(e)

        if not workflow.is_allowed(request.user, constants.WORKFLOW_PERM_SUFFIX_WRITE):
            return HttpResponseForbidden()

        workflow.advance_workflow()

        workflow_serializer = WorkflowSerializer(instance=workflow)

        return Response(
            status=status.HTTP_200_OK,
            content_type="application/json",
            data=workflow_serializer.data,
        )

    @staticmethod
    def _get_workflow(pieuvre_process: PieuvreProcess, obj: WorkflowEnabled):
        # FIXME: improve this logic
        target_workflows = list(
            filter(
                lambda w: pieuvre_process.pk == w.model.pk,
                obj.workflow_instances,
            )
        )

        if not target_workflows or len(target_workflows) > 1:
            # not normal, there are many instances of the same (workflow, pieuvre_process)
            raise Http404(_("Workflow does not exist"))

        target_workflow = target_workflows[0]

        # Consistency check
        # Usefulness TBD?
        if target_workflow.state != target_workflow.get_initial_state():
            raise WorkflowDoesNotExist(_("Workflow does not exist"))

        return target_workflow


class AdvanceWorkflowPermissions(permissions.DjangoModelPermissions):
    """
    This permission class is meant to be used with the AdvanceWorkflowMixin.
    It will check that the user has at least one permission set in `workflow_perms`
    otherwise it will return an HTTP_FORBIDDEN response.
    It must be used with another permission class that will check that the user
    has the rights for the given HTTP methods.
    """

    workflow_perms = []

    def get_required_permissions(self, method, model_cls):
        kwargs = {
            "app_label": model_cls._meta.app_label,
            "model_name": model_cls._meta.model_name,
        }

        return [perm % kwargs for perm in self.workflow_perms]

    def has_permission(self, request, view):
        if view.action != "advance_workflow" or request.method != "POST":
            return False

        user = request.user
        queryset = self._queryset(view)
        perms = self.get_required_permissions(request.method, queryset.model)
        # The AdvanceWorkflowMixin will check that the user has the
        # actual permission for the selected workflow, so we just make sure
        # the user has a write access to at least one of them
        return any(user.has_perm(perm) for perm in perms)

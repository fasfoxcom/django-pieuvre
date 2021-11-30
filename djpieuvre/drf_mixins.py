from django.http import Http404, HttpResponseBadRequest
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

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


class WorkflowDoesNotExits(Exception):
    pass


class AdvanceWorkflowMixin(object):
    """
    The aim of this mixin is to expose an endpoint that should help the frontend to advance a workflow (only from it's
    initial state to the next), having it's PieuvreProcess.
    This implementation only care about the first state.
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
        serializer = AdvanceWorkflowSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        obj = self.get_object()

        try:
            workflow = self._perform_advance_workflow(
                serializer.validated_data.get("workflow"), obj
            )
        except WorkflowDoesNotExits as e:
            return HttpResponseBadRequest(e)

        workflow_serializer = WorkflowSerializer(instance=workflow)

        return Response(
            status=status.HTTP_200_OK,
            content_type="application/json",
            data=workflow_serializer.data,
        )

    @staticmethod
    def _perform_advance_workflow(
        pieuvre_process: PieuvreProcess, obj: WorkflowEnabled
    ):

        target_workflows = list(
            filter(
                lambda w: pieuvre_process.pk == w.model.pk,
                obj.workflow_instances,
            )
        )

        if not target_workflows or len(target_workflows) > 1:
            # not normal, there are many instances of the same (workflow, pieuvre_process)
            raise Http404(_("Workflow not exist"))

        target_workflow = target_workflows[0]

        if target_workflow.state != target_workflow.states[0]:
            raise WorkflowDoesNotExits(_("Workflow not exist"))

        target_workflow.advance_workflow()

        return target_workflow

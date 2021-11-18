from pieuvre import WorkflowEnabled as PieuvreWorkflowEnabled


class WorkflowEnabled(PieuvreWorkflowEnabled):
    """
    This superclass adds a `workflows` property on the inheriting model
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._workflows = []

    @property
    def workflows(self):
        # returns only workflows that suite related to the current model.
        return [w for w in self._workflows]

    @property
    def workflow_instances(self):
        return [w(self) for w in self.workflows]

    @classmethod
    def register_workflow(cls, workflow_class):
        cls._workflows.append(workflow_class)


class RequestInfoMixin:
    """
    Provides simple interface to gather request information within Serializer.
    """

    @property
    def user(self):
        request = self.context.get("request", None)
        if request and hasattr(request, "user"):
            return request.user

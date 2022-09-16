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
        return [w for w in self._workflows if w.applies_to(self)]

    @property
    def workflow_instances(self):
        return [w(self) for w in self.workflows]

    @classmethod
    def register_workflow(cls, workflow_class):
        cls._workflows.append(workflow_class)

    def task_repr(self):
        """
        This method can be implemented to return an user friendly string attached to the tasks list.
        Optionally, fields can be preloaded by filling the select_related attribute.
        """
        return None


class RequestInfoMixin:
    """
    Provides simple interface to gather request information within Serializer.
    """

    @property
    def user(self):
        request = self.context.get("request", None)
        if request and hasattr(request, "user"):
            return request.user

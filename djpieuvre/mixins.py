from pieuvre import WorkflowEnabled as PieuvreWorkflowEnabled


class WorkflowEnabled(PieuvreWorkflowEnabled):
    """
    This superclass adds a `workflows` property on the inheriting model
    """

    _workflows = []

    @property
    def workflows(self):
        return self._workflows

    @property
    def workflow_instances(self):
        # TODO: access permissions. As of now all workflows are returned, but we should only
        # return the ones the user has access to.
        return [w(self) for w in self.workflows]

    @classmethod
    def register_workflow(cls, workflow_class):
        cls._workflows.append(workflow_class)

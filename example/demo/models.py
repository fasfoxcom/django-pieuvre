from django.db import models

from djpieuvre.mixins import WorkflowEnabled


class MyProcess(WorkflowEnabled, models.Model):
    my_property = models.TextField()

    def task_repr(self):
        return self.my_property

    class Meta:
        permissions = [
            ("access_my_first_workflow2", "comment"),
        ]

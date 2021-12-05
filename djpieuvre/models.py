from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from djpieuvre.constants import TASK_STATES
from djpieuvre.mixins import WorkflowEnabled


class PieuvreProcess(WorkflowEnabled, models.Model):
    STATE_FIELD_NAME = "state"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    process_target = GenericForeignKey("content_type", "object_id")
    workflow_name = models.TextField()
    workflow_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(auto_now=True)
    state = models.TextField()

    data = models.JSONField(null=True, blank=True)

    def get_workflow_class(self):
        from djpieuvre.core import get

        workflow = get(self.workflow_name, self.workflow_version)
        if not workflow:
            raise ValueError(f"Workflow {self.workflow_name} is not registered")
        return workflow

    @property
    def workflow_fancy_name(self):
        return self.get_workflow_class().fancy_name

    def __str__(self):
        return (
            f"Process {self.workflow_name} {self.content_type.model}({self.object_id})"
        )

    class Meta:
        unique_together = ("content_type", "object_id", "workflow_name")
        ordering = ("created_at",)


class PieuvreTask(models.Model):
    process = models.ForeignKey(
        PieuvreProcess, on_delete=models.CASCADE, related_name="tasks"
    )
    state = models.CharField(
        choices=TASK_STATES, default=TASK_STATES.CREATED, max_length=128
    )
    name = models.TextField()
    task = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(auto_now=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)
    groups = models.ManyToManyField("auth.Group")

    data = models.JSONField(null=True, blank=True)

    def assign(self, transition, users, groups):
        """
        Takes a pieuvre transition and tries to assign it to some users.
        Override to implement custom behavior.
        """
        if users:
            self.users.set(users)
        if groups:
            self.groups.set(groups)

    def complete(self, transition):
        self.state = TASK_STATES.DONE
        self.process.workflow.run_transition(transition, self)
        self.process.workflow.advance_workflow()

    def __str__(self):
        return f"Task {self.name} {self.process.content_type.model} ({self.process.object_id})"

    class Meta:
        ordering = ("created_at",)

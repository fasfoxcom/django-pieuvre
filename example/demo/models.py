from django.db import models

from djpieuvre.mixins import WorkflowEnabled


class MyProcess(WorkflowEnabled, models.Model):
    my_property = models.TextField()

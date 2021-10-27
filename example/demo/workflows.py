from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from djpieuvre.core import Workflow
from djpieuvre import on_task_assign_group, on_task_assign_user
from .models import MyProcess

User = get_user_model()


class MyFirstWorkflow1(Workflow):
    persist = True
    states = ["created", "submitted", "done"]
    target_model = MyProcess
    transitions = [
        {
            "name": "submit",
            "source": "created",
            "destination": "submitted",
            "manual": False,
        },
        {
            "name": "finish",
            "source": "submitted",
            "destination": "done",
            "manual": True,
        },
    ]

    def default_user(self, task):
        return User.objects.all()


class MyFirstWorkflow2(Workflow):
    persist = True
    states = ["init", "in_progress", "completed"]
    target_model = MyProcess
    transitions = [
        {
            "name": "initialize",
            "source": "init",
            "destination": "in_progress",
            "manual": True,
        },
        {
            "name": "complete",
            "source": "in_progress",
            "destination": "completed",
            "manual": True,
        },
    ]

    @on_task_assign_group("complete")
    def groups_who_can_complete(self, task, transition):
        return Group.objects.filter(name__startswith="Completers")

    @on_task_assign_user("complete")
    def users_who_can_complete(self, task, transition):
        return User.objects.filter(groups__name__startswith="Completers")

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from extended_choices import Choices

from djpieuvre.core import Workflow
from djpieuvre import on_task_assign_group, on_task_assign_user
from .models import MyProcess
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class MyFirstWorkflow1(Workflow):
    persist = True
    states = Choices(
        ("CREATED", "created", "Created State"),
        ("SUBMITTED", "submitted", "Submitted State"),
        ("DONE", "done", "Done State"),
    )
    target_model = MyProcess
    fancy_name = _("My first workflow")
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

    def default_user(self):
        return User.objects.all()


class MyFirstWorkflow2(Workflow):
    persist = True
    states = ["init", "in_progress", "completed"]
    target_model = MyProcess
    fancy_name = _("My first workflow 2")
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
    def groups_who_can_complete(self, transition):
        return Group.objects.filter(name__startswith="Completers")

    @on_task_assign_user("complete")
    def users_who_can_complete(self, transition):
        return User.objects.filter(groups__name__startswith="Completers")


class MyFirstWorkflow3(Workflow):
    persist = True
    states = ["init", "progressing", "completed"]
    target_model = MyProcess
    fancy_name = _("My first workflow 3")
    transitions = [
        {
            "name": "initialize",
            "source": "init",
            "destination": "progressing",
            "manual": True,
        },
        {
            "name": "complete",
            "source": "progressing",
            "destination": "completed",
            "manual": True,
        },
    ]

    @on_task_assign_group("complete")
    def groups_who_can_complete(self, transition):
        return Group.objects.filter(name__startswith="Completers")

    @on_task_assign_user("complete")
    def users_who_can_complete(self, transition):
        return User.objects.filter(groups__name__startswith="Completers")


class MyFirstWorkflow4(Workflow):
    persist = True
    states = ["init", "edited", "submitted", "accepted", "withdrawn"]
    target_model = MyProcess
    fancy_name = _("My first workflow 4")
    transitions = [
        {
            "name": "initialize",
            "source": "init",
            "destination": "edited",
            "manual": False,
            "label": "source event",
            "description": "initialize the process",
        },
        {
            "name": "submit",
            "source": "edited",
            "destination": "submitted",
            "manual": True,
            "label": "submit",
            "description": "Submit a paper",
        },
        {
            "name": "accept",
            "source": "submitted",
            "destination": "accepted",
            "manual": True,
            "label": "accept",
            "description": "accept a paper",
        },
        {
            "name": "reject",
            "source": "submitted",
            "destination": "edited",
            "manual": True,
            "label": "reject",
            "description": "reject a paper",
        },
        {
            "name": "withdraw",
            "source": "submitted",
            "destination": "withdrawn",
            "manual": True,
            "label": "Withdrawn",
            "description": "Complete deletion",
        },
    ]

    @on_task_assign_group("submit")
    def groups_who_can_submit(self, transition):
        return Group.objects.filter(name__startswith="Researcher")

    @on_task_assign_group("accept")
    def groups_who_can_accept(self, transition):
        return Group.objects.filter(name__startswith="Evaluator")

    @on_task_assign_group("reject")
    def groups_who_can_reject(self, transition):
        return Group.objects.filter(name__startswith="Evaluator")

    @on_task_assign_group("withdraw")
    def groups_who_can_withdraw(self, transition):
        return Group.objects.filter(name__startswith="Withdraw")


class MyFirstWorkflow5(Workflow):
    persist = True
    states = [
        "init",
        "edited",
        "submitted",
        "accepted",
        "withdrawn",
        "published",
        "commented",
        "archived",
    ]
    target_model = MyProcess
    transitions = [
        {
            "name": "initialize",
            "source": "init",
            "destination": "edited",
            "manual": False,
            "label": "source event",
            "description": "initialize the process",
        },
        {
            "name": "submit",
            "source": "edited",
            "destination": "submitted",
            "manual": False,
            "label": "submit",
            "description": "Submit a paper",
        },
        {
            "name": "accept",
            "source": "submitted",
            "destination": "accepted",
            "manual": True,
            "label": "accept",
            "description": "accept a paper",
        },
        {
            "name": "reject",
            "source": "submitted",
            "destination": "edited",
            "manual": True,
            "label": "reject",
            "description": "reject a paper",
        },
        {
            "name": "publish",
            "source": "accepted",
            "destination": "published",
            "manual": False,
            "label": "Published",
            "description": "Publish",
        },
        {
            "name": "comment",
            "source": "published",
            "destination": "commented",
            "manual": True,
            "label": "commented",
            "description": "commented",
        },
        {
            "name": "archive",
            "source": "commented",
            "destination": "archived",
            "manual": True,
            "label": "archived",
            "description": "archived",
        },
    ]

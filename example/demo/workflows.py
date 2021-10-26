from djpieuvre.core import Workflow


class MyFirstWorkflow1(Workflow):
    persist = True
    states = ["created", "submitted", "done"]
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


class MyFirstWorkflow2(Workflow):
    persist = True
    states = ["init", "in_progress", "completed"]
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
            "manual": False,
        },
    ]

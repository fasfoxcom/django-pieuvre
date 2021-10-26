from extended_choices import Choices

TASK_STATES = Choices(
    ("CREATED", "created", "Created"),
    ("ASSIGNED", "assigned", "Assigned"),
    ("STARTED", "started", "Started"),
    ("DONE", "done", "Done"),
)

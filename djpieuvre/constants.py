from extended_choices import Choices

TASK_STATES = Choices(
    ("CREATED", "created", "Created"),
    ("ASSIGNED", "assigned", "Assigned"),
    ("STARTED", "started", "Started"),
    ("DONE", "done", "Done"),
)

ON_TASK_ASSIGN_USER_HOOK = "_on_task_assign_user_hook"
ON_TASK_ASSIGN_GROUP_HOOK = "_on_task_assign_group_hook"

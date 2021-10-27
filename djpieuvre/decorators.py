from pieuvre.core import BaseDecorator

from djpieuvre.constants import ON_TASK_ASSIGN_GROUP_HOOK, ON_TASK_ASSIGN_USER_HOOK


class OnTaskAssignGroup(BaseDecorator):
    """
    Wrap a function with this decorator to run it after
    a task is created and return a group to assign.

    Example:

    .. code-block::

       @on_task_assign_group(ROCKET_STATES.ON_LAUNCHPAD)
       def groups_who_can_launch(self, result):
           return Group.objects.filter(name__contains="MISSION CONTROL")
    """

    type = ON_TASK_ASSIGN_GROUP_HOOK


class OnTaskAssignUser(BaseDecorator):
    """
    Wrap a function with this decorator to run it after
    a task is created and return a group to assign.

    Example:

    .. code-block::

       @on_task_assign_user(ROCKET_STATES.ON_LAUNCHPAD)
       def users_who_can_launch(self, result):
           return User.objects.filter(groups__name__contains="MISSION CONTROL")
    """

    type = ON_TASK_ASSIGN_USER_HOOK

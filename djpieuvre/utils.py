import re
from functools import cache

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q


# from https://stackoverflow.com/a/1176023/13837279
def camel_to_snake(value):
    value = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", value).lower()


@cache
def get_app_name(model):
    # ContentType uses a cache on it's manager
    # so it only queries app_name once per model.
    if not model:
        return

    return ContentType.objects.get_for_model(model).app_label


def get_task_predicate(user):
    # User is always defined in our case, thanks to the IsAuthenticated permission, but this allows
    # a superclass to remove the need for auth
    # First filter: the task is not assigned at all. Might apply to unauthenticated users
    f = Q(users__isnull=True) & Q(groups__isnull=True)
    if user:
        f = (
            f
            | Q(users=user)  # Or current user is assigned
            | Q(  # Or current user belongs to a group that is assigned
                groups__in=user.groups.all()
            )
        )
    return f

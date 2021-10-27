import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from djpieuvre.models import PieuvreTask
from .models import MyProcess
from .workflows import MyFirstWorkflow1, MyFirstWorkflow2


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Faker("user_name")
    first_name = factory.Faker("first_name")
    email = factory.Faker("email")

    class Meta:
        model = get_user_model()


class GroupFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("company")

    class Meta:
        model = Group


class TasksTests(APITestCase):
    @staticmethod
    def _advance_and_reload_workflow(workflow_class, instance, *args, **kwargs):
        wf = workflow_class(instance, *args, **kwargs)
        wf.advance_workflow()
        instance.refresh_from_db()
        return workflow_class(instance)

    def test_workflow_is_persisted(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(MyFirstWorkflow1, process)
        # We went from created to submitted
        self.assertEqual(wf.state, "submitted")

    def test_workflow_cant_advance_on_its_own(self):
        # Not sure where this user comes from!
        user = User.objects.first()
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, initial_state="submitted"
        )
        # We did not advance because the transition is manual
        self.assertEqual(wf.state, "submitted")
        # There should be a Task now
        task = PieuvreTask.objects.first()
        self.assertIsNotNone(task)
        self.assertEqual(task.task, "finish")
        self.assertEqual(task.process, wf.model)
        self.assertEqual(task.state, "created")
        # Make sure that the user is assigned (because this workflows has a default assignment)
        self.assertEqual(task.groups.count(), 0)
        self.assertEqual(task.users.first(), user)
        # We can complete the task
        task.complete()
        self.assertEqual(task.state, "done")

    def test_workflow_task_assignment(self):
        users = [UserFactory() for i in range(20)]
        user = User.objects.last()
        groups = [GroupFactory() for i in range(10)]
        group = GroupFactory(name="Completers Team")
        user.groups.add(group)
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow2, process, initial_state="in_progress"
        )
        # There should be a task, assigned to the user and the group
        task = PieuvreTask.objects.first()
        self.assertIsNotNone(task)
        self.assertEqual(list(task.users.all()), [user])
        self.assertEqual(list(task.groups.all()), [group])


class AuthenticatedTasksTests(TasksTests):
    def setUp(self, password=None):
        self.user = UserFactory()
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_user_can_get_tasks(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, initial_state="submitted"
        )
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        task = PieuvreTask.objects.first()
        # Now try to complete the task
        # GET should be forbidden
        response = self.client.get(
            reverse("pieuvretask-complete", kwargs={"pk": task.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # But POST should be allowed
        response = self.client.post(
            reverse("pieuvretask-complete", kwargs={"pk": task.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.state, "done")

    def test_user_cant_get_tasks_assigned_to_someone_else(self):
        user = UserFactory()
        group = GroupFactory(name="Completers Team")
        user.groups.add(group)
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow2, process, initial_state="in_progress"
        )
        # user has been assigned the task because he is in the Completers Team
        # but self.user is not assigned, and therefore should not be able to even see the task
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 0)

        # But obviously, user should
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

        # Even if he "just" belongs to the group
        task = PieuvreTask.objects.first()
        task.users.clear()
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

        # And also if the task is not assigned to anyone
        task.groups.clear()
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

        # And in that case, of course, self.user should also be able to access it
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_user_can_get_workflows(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, initial_state="submitted"
        )
        response = self.client.get(
            reverse("myprocess-workflows", kwargs={"pk": process.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        js = response.json()
        self.assertEqual(len(js["workflows"]), 2)
        self.assertEqual(js["workflows"][0]["state"], "submitted")
        self.assertEqual(js["workflows"][0]["transitions"][0]["name"], "finish")

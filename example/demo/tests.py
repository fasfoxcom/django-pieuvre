from django.contrib.auth import get_user_model
from django.urls import reverse
import factory
from rest_framework import status
from rest_framework.test import APITestCase

from djpieuvre.models import PieuvreTask
from .models import MyProcess
from .workflows import MyFirstWorkflow1


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Faker("user_name")
    first_name = factory.Faker("first_name")
    email = factory.Faker("email")

    class Meta:
        model = get_user_model()


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
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, default_state="submitted"
        )
        # We did not advance because the transition is manual
        self.assertEqual(wf.state, "submitted")
        # There should be a Task now
        task = PieuvreTask.objects.first()
        self.assertIsNotNone(task)
        self.assertEqual(task.task, "finish")
        self.assertEqual(task.process, wf.model)
        self.assertEqual(task.state, "created")
        # We can complete the task
        task.complete()
        self.assertEqual(task.state, "done")


class AuthenticatedTasksTests(TasksTests):
    def setUp(self, password=None):
        self.user = UserFactory()
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_user_can_get_tasks(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, default_state="submitted"
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

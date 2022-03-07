import time

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from djpieuvre.constants import TASK_STATES
from djpieuvre.models import PieuvreTask
from .models import MyProcess
from .workflows import (
    MyFirstWorkflow1,
    MyFirstWorkflow2,
    MyFirstWorkflow3,
    MyFirstWorkflow4,
    MyFirstWorkflow5,
)


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
        self.assertEqual(task.task, "submitted")
        self.assertEqual(task.process, wf.model)
        self.assertEqual(task.state, "created")
        # Make sure that the user is assigned (because this workflows has a default assignment)
        self.assertEqual(task.groups.count(), 0)
        self.assertEqual(task.users.first(), user)
        # We can complete the task
        task.complete("finish")
        self.assertEqual(task.state, "done")
        self.assertEqual(task.task, "submitted")

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
        process = MyProcess.objects.create(my_property="unique-prop")
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, initial_state="submitted"
        )
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        j = response.json()

        self.assertEqual(len(j), 1)
        task_json = j[0]
        self.assertEqual(task_json["process_name"], "MyFirstWorkflow1")
        self.assertEqual(task_json["process_fancy_name"], "My first workflow")
        self.assertEqual(task_json["name"], "Submitted State")
        self.assertEqual(task_json["instance_repr"], "unique-prop")

        task = PieuvreTask.objects.first()
        # Now try to complete the task
        # GET should be forbidden
        response = self.client.get(
            reverse("pieuvretask-complete", kwargs={"pk": task.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # But POST should be allowed
        response = self.client.post(
            reverse("pieuvretask-complete", kwargs={"pk": task.pk}),
            data={"transition": "finish"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.state, "done")
        process.refresh_from_db()
        self.assertEqual(process.workflow_instances[0].state, "done")

        # Cannot execute transition twice
        response = self.client.post(
            reverse("pieuvretask-complete", kwargs={"pk": task.pk}),
            data={"transition": "report"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        task = PieuvreTask.objects.get(task="done")
        self.assertEqual(task.state, "created")
        process.refresh_from_db()
        self.assertEqual(process.workflow_instances[0].state, "done")

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

    def test_user_can_only_get_authorized_workflows(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow1, process, initial_state="submitted"
        )
        response = self.client.get(
            reverse("myprocess-workflows", kwargs={"pk": process.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.json()
        self.assertEqual(len(task["workflows"]), 4)
        self.assertEqual(task["workflows"][0]["state"], "submitted")
        for wrkf in task["workflows"]:
            self.assertNotEqual(wrkf["name"], MyFirstWorkflow2.name)

    def test_unauthorized_user_cannot_get_manual_transition(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow3, process, initial_state="progressing"
        )
        response = self.client.get(
            reverse("myprocess-workflows", kwargs={"pk": process.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.json()
        self.assertEqual(len(task["workflows"]), 4)

        self.assertEqual(task["workflows"][0]["state"], "created")
        self.assertEqual(len(task["workflows"][0]["transitions"]), 1)

        self.assertEqual(task["workflows"][1]["state"], "progressing")
        self.assertEqual(len(task["workflows"][1]["transitions"]), 0)

        # Make the user a completer
        GroupFactory(name="Completers Team")
        self.user.groups.add(Group.objects.get(name="Completers Team"))

        response = self.client.get(
            reverse("myprocess-workflows", kwargs={"pk": process.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.json()

        self.assertEqual(task["workflows"][0]["state"], "created")
        self.assertEqual(len(task["workflows"][0]["transitions"]), 1)

        # user can get complete transition since he is a completer
        self.assertEqual(task["workflows"][1]["state"], "progressing")
        self.assertEqual(len(task["workflows"][1]["transitions"]), 1)

    def test_caching(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(MyFirstWorkflow3, process)
        GroupFactory(name="Completers Team")
        wf.groups_who_can_complete.cache_clear()
        with self.assertNumQueries(1):
            len(wf.groups_who_can_complete(tuple(wf.transitions[1].items())))

        self.assertEqual(wf.groups_who_can_complete.cache_info().hits, 0)
        for i in range(1, 10):
            with self.assertNumQueries(0):
                # make sure the groups are retrieved from the cache.
                len(wf.groups_who_can_complete(tuple(wf.transitions[1].items())))
            self.assertEqual(wf.groups_who_can_complete.cache_info().hits, i)

    def test_task_detail_view_contains_next_available_transitions(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow4, process, initial_state="edited"
        )
        # The current user is a researcher
        GroupFactory(name="Researcher Team")
        self.user.groups.add(Group.objects.get(name="Researcher Team"))
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertNotIn("transitions", response.data[0])

        response = self.client.get(
            reverse("pieuvretask-detail", args=[response.data[0]["id"]])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.data
        self.assertIn("transitions", task)
        self.assertEqual(len(task["transitions"]), 1)
        self.assertEqual(task["task"], "edited")

    def test_user_should_be_able_to_choose_transition_to_be_executed(self):
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow4, process, initial_state="submitted"
        )
        # The current user is a researcher
        GroupFactory(name="Evaluator Team")
        self.user.groups.add(Group.objects.get(name="Evaluator Team"))
        response = self.client.get(reverse("pieuvretask-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

        response = self.client.get(
            reverse("pieuvretask-detail", args=[response.data[0]["id"]])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.data
        self.assertIn("transitions", task)
        self.assertEqual(len(task["transitions"]), 2)

        self.assertEqual(task["transitions"][0]["name"], "accept")
        self.assertEqual(task["transitions"][1]["name"], "reject")

        response = self.client.post(
            reverse("pieuvretask-complete", kwargs={"pk": task["id"]}),
            data={"transition": "reject", "reason": "bad robot"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        task = response.data
        response = self.client.get(
            reverse("myprocess-workflows", kwargs={"pk": task["id"]})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        process = response.data
        self.assertEqual(process["workflows"][2]["state"], "edited")

        response = self.client.get(
            reverse("pieuvretask-detail", kwargs={"pk": task["id"]})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.data
        self.assertEqual(task["data"]["reason"], "bad robot")

    def test_task_filter(self):
        process1 = MyProcess.objects.create()
        process2 = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow3, process1, initial_state="progressing"
        )
        self.assertTrue(wf.model.tasks.exists())
        task = wf.model.tasks.first()
        task.complete("complete")
        task.save()
        self.assertEqual(task.state, TASK_STATES.DONE)

        wf = self._advance_and_reload_workflow(MyFirstWorkflow3, process2)
        self.assertEqual(PieuvreTask.objects.count(), 2)
        task = wf.model.tasks.order_by("-created_at").first()
        self.assertEqual(task.state, TASK_STATES.CREATED)

        response = self.client.get(reverse("pieuvretask-list"))

        js = response.data
        self.assertEqual(len(js), 2)
        self.assertEqual(js[0]["id"], task.pk)
        response = self.client.get(
            reverse("pieuvretask-list"), data={"status": TASK_STATES.DONE}
        )
        js = response.data
        self.assertEqual(len(js), 1)


class GatewayTest(AuthenticatedTasksTests):
    def test_workflow_gateway_flow(self):
        # we test here that we can leave a source state when there are multiple manual transitions that can be applied
        # to go to the next state
        process = MyProcess.objects.create()
        wf = self._advance_and_reload_workflow(
            MyFirstWorkflow4, process, initial_state="submitted"
        )

        wf.advance_workflow()

        # we create a task which have this state as source
        task = PieuvreTask.objects.first()
        self.assertEqual(task.process.state, "submitted")

        g = GroupFactory(name="Evaluator")
        self.user.groups.add(g)

        r = self.client.get(reverse("pieuvretask-list"))

        # let's zoom into the task
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0]["task"], "submitted")

        self.assertEqual(r.json()[0]["model"], "myprocess")
        self.assertEqual(r.json()[0]["model_id"], str(wf.process_target.id))

        task = r.json()[0]
        r = self.client.get(reverse("pieuvretask-detail", args=[task["id"]]))
        # the current user should have a task "submitted"

        self.assertEqual(r.status_code, 200)
        task_detail = r.json()
        self.assertEqual(task_detail["task"], "submitted")
        self.assertEqual(len(task_detail["transitions"]), 2)

        transitions = task_detail["transitions"]
        self.assertEqual(transitions[0]["name"], "accept")
        self.assertEqual(transitions[1]["name"], "reject")

        r = self.client.post(
            reverse("pieuvretask-complete", kwargs={"pk": task_detail["id"]}),
            data={"transition": "accept"},
        )

        self.assertEqual(r.status_code, 200)

        bd_task = PieuvreTask.objects.get(pk=task_detail["id"])
        self.assertEqual(bd_task.state, "done")
        wf.model.refresh_from_db()

        self.assertEqual(wf.model.state, "accepted")


class AdvanceWorkflowTest(APITestCase):
    def test_can_advance_workflow_from_api(self):
        process = MyProcess.objects.create()
        wflw = MyFirstWorkflow1(model=process)
        self.assertEqual(wflw.state, "created")
        r = self.client.post(
            reverse("myprocess-advance-workflow", args=[process.pk]),
            data={"workflow": wflw.model.pk},
        )

        self.assertEqual(r.status_code, 200)
        wflw.model.refresh_from_db()
        self.assertEqual(wflw.state, "submitted")

    def test_try_to_start_workflow_on_already_running_workflow(self):
        process = MyProcess.objects.create()
        wflw = MyFirstWorkflow4(model=process, initial_state="edited")
        self.assertEqual(wflw.state, "edited")
        r = self.client.post(
            reverse("myprocess-advance-workflow", args=[process.pk]),
            data={"workflow": wflw.model.pk},
        )

        self.assertEqual(r.status_code, 400)
        wflw.model.refresh_from_db()
        self.assertEqual(wflw.state, "edited")

    def test_auto_advance_workflow(self):
        process = MyProcess.objects.create()
        workflow = MyFirstWorkflow5(model=process)

        self.assertEqual(workflow.state, "init")

        workflow.advance_workflow()

        workflow.model.refresh_from_db()
        self.assertEqual(workflow.state, "submitted")

        task = PieuvreTask.objects.all()[0]

        task.complete("accept")
        workflow.model.refresh_from_db()
        self.assertEqual(workflow.state, "published")

        task = PieuvreTask.objects.all()[1]
        task.complete("comment")
        workflow.model.refresh_from_db()
        self.assertEqual(workflow.state, "commented")

        task = PieuvreTask.objects.all()[2]
        task.complete("archive")
        workflow.model.refresh_from_db()
        self.assertEqual(workflow.state, "archived")


class WorkflowViewTest(APITestCase):
    def test_can_retrieve_workflow_detail_on_model(self):
        process = MyProcess.objects.create()
        wflw = MyFirstWorkflow4(model=process, initial_state="edited")

        r = self.client.get(reverse("myprocess-detail", args=[process.pk]))

        self.assertEqual(r.status_code, 200)
        current_wflw = list(
            filter(lambda x: x["pk"] == str(wflw.model.pk), r.json()["workflows"])
        )[0]

        self.assertEqual(current_wflw["name"], "MyFirstWorkflow4")
        self.assertEqual(current_wflw["state"], "edited")
        self.assertEqual(current_wflw["fancy_name"], "My first workflow 4")

        process = MyProcess.objects.create()
        wflw = MyFirstWorkflow1(model=process)
        r = self.client.get(reverse("myprocess-detail", args=[process.pk]))

        current_wflw = list(
            filter(lambda x: x["pk"] == str(wflw.model.pk), r.json()["workflows"])
        )[0]
        self.assertEqual(current_wflw["name"], "MyFirstWorkflow1")
        self.assertEqual(current_wflw["state"], "created")
        self.assertEqual(current_wflw["fancy_name"], "My first workflow")
        self.assertEqual(
            current_wflw["states"],
            {
                "created": "Created State",
                "submitted": "Submitted State",
                "done": "Done State",
                "reported": "Reporting Done State"
            },
        )

    def test_can_list_workflow_on_model(self):
        process = MyProcess.objects.create()

        r = self.client.get(reverse("myprocess-detail", args=[process.pk]))

        self.assertEqual(r.status_code, 200)

        workflows = r.json()["workflows"]

        self.assertEqual(len(workflows), 4)

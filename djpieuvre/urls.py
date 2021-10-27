# Create a router and register our viewsets with it.
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from djpieuvre import views

router = DefaultRouter()
router.register(r"tasks", views.TaskViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

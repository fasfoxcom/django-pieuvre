from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import MyProcessViewSet

router = DefaultRouter()
router.register(r"myprocess", MyProcessViewSet)
urlpatterns = [
    path("", include(router.urls)),
]

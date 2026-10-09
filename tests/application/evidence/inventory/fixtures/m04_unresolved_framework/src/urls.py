from django.urls import path


def index() -> str:
    return "ok"


urlpatterns = [path("home/", index)]

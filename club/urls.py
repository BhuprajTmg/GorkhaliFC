from django.urls import path

from . import views

app_name = "club"

urlpatterns = [
    path("", views.home, name="home"),
    path("players/<slug:slug>/", views.player_detail, name="player_detail"),
]

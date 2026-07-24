from django.urls import path

from . import views

app_name = "club"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("players/", views.players, name="players"),
    path("players/<slug:slug>/", views.player_detail, name="player_detail"),
    path("schedule/", views.schedule, name="schedule"),
    path("photos/", views.photos, name="photos"),
    path("contact/", views.contact, name="contact"),
]

from django.contrib.auth import views as auth
from django.urls import path
from . import views
urlpatterns = [
    path("", views.home, name="home"),
    path("matches/", views.matches, name="matches"),
    path("members/<int:pk>/", views.member_detail, name="member"),
    path("members/<int:pk>/like/", views.like, name="like"),
    path("likes/", views.my_likes, name="my_likes"),
    path("messages/", views.inbox, name="inbox"),
    path("messages/<int:pk>/", views.thread, name="thread"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("events/", views.events, name="events"),
    path("services/", views.services, name="services"),
    path("premium/", views.premium, name="premium"),
]

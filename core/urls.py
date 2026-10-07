from django.contrib.auth import views as auth
from django.urls import path
from . import views, views_content, views_market
urlpatterns = [
    path("", views.home, name="home"),
    path("matches/", views.matches, name="matches"),
    path("members/<int:pk>/", views.member_detail, name="member"),
    path("members/<int:pk>/like/", views.like, name="like"),
    path("members/<int:pk>/shortlist/", views.shortlist, name="shortlist"),
    path("members/<int:pk>/report/", views.report, name="report"),
    path("likes/", views.my_likes, name="my_likes"),
    path("messages/", views.inbox, name="inbox"),
    path("messages/<int:pk>/", views.thread, name="thread"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("events/", views_content.events, name="events"),
    path("events/<int:pk>/register/", views_content.event_register, name="event_register"),
    path("services/", views_market.services, name="services"),
    path("services/<slug:slug>/", views_market.advert, name="advert"),
    path("services/<slug:slug>/wishlist/", views_market.wishlist, name="wishlist"),
    path("services/<slug:slug>/inquire/", views_market.inquire, name="inquire"),
    path("services/<slug:slug>/review/", views_market.review, name="review"),
    path("articles/", views_content.articles, name="articles"),
    path("articles/<slug:slug>/", views_content.article, name="article"),
    path("premium/", views_content.premium, name="premium"),
]

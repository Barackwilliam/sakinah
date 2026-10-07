from django.urls import path
from . import views
urlpatterns = [
    path("", views.overview, name="dashboard"),
    path("report.csv", views.report_csv, name="dash_report"),
    path("members/", views.members, name="dash_members"),
    path("members/<int:pk>/action/", views.member_action, name="dash_member_action"),
    path("communications/", views.communications, name="dash_comms"),
    path("payments/", views.payments, name="dash_payments"),
    path("payments/export.csv", views.payments_csv, name="dash_payments_csv"),
    path("payments/<int:pk>/action/", views.payment_action, name="dash_payment_action"),
    path("payments/<int:pk>/receipt/", views.receipt, name="dash_receipt"),
    path("search/", views.search, name="dash_search"),
]

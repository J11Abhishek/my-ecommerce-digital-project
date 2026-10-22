from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("<str:order_number>/", views.process_payment, name="process"),
    path("<str:order_number>/retry/", views.retry_payment, name="retry"),
]

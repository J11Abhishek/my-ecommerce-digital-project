"""URLs for the accounts app (BRD §31)."""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Profile
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path(
        "profile/password/",
        login_required(views.password_change_view),
        name="password_change",
    ),
    path(
        "profile/password/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    # Addresses
    path("addresses/", views.address_list, name="address_list"),
    path("addresses/add/", views.address_create, name="address_add"),
    path("addresses/<int:pk>/edit/", views.address_update, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
    path("addresses/<int:pk>/default/", views.address_set_default, name="address_set_default"),
]

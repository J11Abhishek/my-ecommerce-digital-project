"""Views for registration, login, profile and addresses (BRD §5, §6, §20, §21)."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AddressForm, LoginForm, ProfileForm, RegisterForm
from .models import Address

SAFE_NEXT = "/"


def _safe_next(request):
    """Only follow internal URLs after login/register (security)."""
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def register(request):
    """FR-01: create a customer account."""
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, f"Welcome to ShopSphere, {user.first_name}!")
            return redirect(_safe_next(request) or reverse("accounts:profile"))
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


class StoreLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse("core:home")


login_view = StoreLoginView.as_view()


class StorePasswordChangeView(auth_views.PasswordChangeView):
    """Password change with a namespaced success URL."""

    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")


password_change_view = StorePasswordChangeView.as_view()


@login_required
def profile(request):
    """Show the customer's profile, default address and recent orders."""
    from orders.models import Order  # local import avoids a circular import

    user = request.user
    addresses = user.addresses.all()
    recent_orders = Order.objects.filter(user=user)[:5]
    return render(
        request,
        "accounts/profile.html",
        {
            "user_obj": user,
            "addresses": addresses,
            "default_address": next((a for a in addresses if a.is_default), None),
            "recent_orders": recent_orders,
        },
    )


@login_required
def profile_edit(request):
    form = ProfileForm(instance=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
def address_list(request):
    return render(
        request,
        "accounts/address_list.html",
        {"addresses": request.user.addresses.all()},
    )


@login_required
def address_create(request):
    form = AddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        if not request.user.addresses.exists():
            address.is_default = True
        address.save()
        messages.success(request, "Address saved.")
        return redirect(request.GET.get("next") or "accounts:address_list")
    return render(request, "accounts/address_form.html", {"form": form, "title": "Add address"})


@login_required
def address_update(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Address updated.")
        return redirect("accounts:address_list")
    return render(
        request,
        "accounts/address_form.html",
        {"form": form, "address": address, "title": "Edit address"},
    )


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    was_default = address.is_default
    address.delete()
    if was_default:
        remaining = request.user.addresses.first()
        if remaining:
            remaining.is_default = True
            remaining.save(update_fields=["is_default"])
    messages.success(request, "Address removed.")
    return redirect("accounts:address_list")


@login_required
@require_POST
def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save()
    messages.success(request, f"{address.label} is now your default address.")
    return redirect(request.POST.get("next") or "accounts:address_list")

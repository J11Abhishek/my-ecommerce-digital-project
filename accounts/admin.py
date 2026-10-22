from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, Profile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "first_name", "last_name", "phone", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_superuser", "is_active"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    readonly_fields = ["date_joined", "last_login"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "has_image", "created_at"]
    list_select_related = ["user"]

    @admin.display(boolean=True, description="Image")
    def has_image(self, obj):
        return bool(obj.profile_image)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["label", "full_name", "user", "city", "state", "pin_code", "address_type", "is_default"]
    list_filter = ["address_type", "is_default"]
    search_fields = ["full_name", "user__email", "city", "pin_code"]
    list_select_related = ["user"]

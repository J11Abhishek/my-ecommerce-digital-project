"""Accounts app: custom user (email login), profile and saved addresses.

Covers BRD sections 1 (Registration), 6 (Login), 20 (Profile) and
21 (Address Management).
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from .managers import UserManager

phone_validator = RegexValidator(
    regex=r"^[0-9+\-\s()]{6,20}$",
    message="Enter a valid phone number (6-20 digits).",
)


class User(AbstractUser):
    """User identified by e-mail instead of username (BRD FR-01)."""

    email = models.EmailField("email address", unique=True)
    username = None  # e-mail replaces the username
    phone = models.CharField(
        "phone number", max_length=20, blank=True, validators=[phone_validator]
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.email

    def get_absolute_url(self):
        return reverse("accounts:profile")


class Profile(models.Model):
    """Extra information attached to every user (BRD §20)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_image = models.ImageField(upload_to="profiles/", blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.email}"


class Address(models.Model):
    """A saved delivery address. A user may store many (BRD §21)."""

    class AddressType(models.TextChoices):
        HOME = "HOME", "Home"
        OFFICE = "OFFICE", "Office"
        OTHER = "OTHER", "Other"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(
        max_length=50, default="Home", help_text="e.g. Home, Office"
    )
    full_name = models.CharField(max_length=150, validators=[MinLengthValidator(2)])
    phone = models.CharField(max_length=20, validators=[phone_validator])
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pin_code = models.CharField(
        "PIN code", max_length=10, validators=[RegexValidator(r"^[0-9]{4,10}$")]
    )
    country = models.CharField(max_length=100, default="India")
    address_type = models.CharField(
        max_length=10, choices=AddressType.choices, default=AddressType.HOME
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.label} - {self.full_name} ({self.city})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(user=self.user).exclude(pk=self.pk).update(
                is_default=False
            )

    @property
    def one_line(self):
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.pin_code,
            self.country,
        ]
        return ", ".join(p for p in parts if p)


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Guarantee a Profile row exists for every user."""
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)

"""Accounts tests: registration, login, profile, addresses (BRD §5, §6, §20, §21)."""

from django.test import TestCase
from django.urls import reverse

from .models import Address, Profile, User


class RegistrationTests(TestCase):
    def test_registration_creates_user_and_profile(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Asha",
                "last_name": "Menon",
                "email": "asha@example.com",
                "phone": "9876543210",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
            },
        )
        user = User.objects.get(email="asha@example.com")
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertTrue(user.check_password("Str0ngPass!23"))

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(email="dupe@example.com", password="Passw0rd!")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "A", "last_name": "B", "email": "dupe@example.com",
                "password1": "Str0ngPass!23", "password2": "Str0ngPass!23",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "A", "last_name": "B", "email": "new@example.com",
                "password1": "Str0ngPass!23", "password2": "Different!23",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "A", "last_name": "B", "email": "weak@example.com",
                "password1": "12345", "password2": "12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="weak@example.com").exists())


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="login@example.com", password="Passw0rd!", first_name="Lee"
        )

    def test_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "login@example.com", "password": "Passw0rd!"},
        )
        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "login@example.com", "password": "nope"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_open_redirect_is_not_followed(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "login@example.com", "password": "Passw0rd!", "next": "https://evil.example.com"},
        )
        self.assertRedirects(response, reverse("core:home"))

    def test_safe_next_is_followed(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "login@example.com", "password": "Passw0rd!", "next": "/orders/my-orders/"},
        )
        self.assertRedirects(response, "/orders/my-orders/")

    def test_logout(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="me@example.com", password="Passw0rd!", first_name="Me", last_name="Too"
        )
        self.client.force_login(self.user)

    def test_profile_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)

    def test_profile_page(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "me@example.com")

    def test_profile_update(self):
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {"first_name": "New", "last_name": "Name", "email": "me@example.com", "phone": "9000000000"},
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")

    def test_password_change(self):
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "Passw0rd!",
                "new_password1": "N3wStrongPass!",
                "new_password2": "N3wStrongPass!",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("N3wStrongPass!"))


class AddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="addr@example.com", password="Passw0rd!")
        self.client.force_login(self.user)
        self.payload = {
            "label": "Office", "full_name": "Me Too", "phone": "9876543210",
            "address_line1": "1 Residency Road", "address_line2": "Floor 2",
            "city": "Bengaluru", "state": "Karnataka", "pin_code": "560025",
            "country": "India", "address_type": "OFFICE", "is_default": "",
        }

    def test_first_address_becomes_default(self):
        self.client.post(reverse("accounts:address_add"), self.payload)
        self.assertTrue(self.user.addresses.get().is_default)

    def test_setting_default_unsets_the_previous_one(self):
        first = Address.objects.create(
            user=self.user, full_name="A", phone="9876543210", address_line1="X",
            city="Bengaluru", state="Karnataka", pin_code="560001", is_default=True,
        )
        second = Address.objects.create(
            user=self.user, full_name="B", phone="9876543210", address_line1="Y",
            city="Bengaluru", state="Karnataka", pin_code="560002", is_default=True,
        )
        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    def test_cannot_edit_another_users_address(self):
        other = User.objects.create_user(email="other@example.com", password="Passw0rd!")
        address = Address.objects.create(
            user=other, full_name="A", phone="9876543210", address_line1="X",
            city="B", state="K", pin_code="560001",
        )
        response = self.client.get(reverse("accounts:address_edit", args=[address.pk]))
        self.assertEqual(response.status_code, 404)

    def test_invalid_pin_code_rejected(self):
        self.payload["pin_code"] = "abc"
        response = self.client.post(reverse("accounts:address_add"), self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Address.objects.exists())

    def test_delete_promotes_another_default(self):
        first = Address.objects.create(
            user=self.user, full_name="A", phone="9876543210", address_line1="X",
            city="B", state="K", pin_code="560001", is_default=True,
        )
        second = Address.objects.create(
            user=self.user, full_name="B", phone="9876543210", address_line1="Y",
            city="B", state="K", pin_code="560002",
        )
        self.client.post(reverse("accounts:address_delete", args=[first.pk]))
        second.refresh_from_db()
        self.assertTrue(second.is_default)

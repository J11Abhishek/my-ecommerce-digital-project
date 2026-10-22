"""Forms for registration, profile and address management (BRD §5, §20, §21)."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Address, User


class RegisterForm(UserCreationForm):
    """Registration form: first name, last name, e-mail, password, confirm."""

    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "First name"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "Last name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}))
    phone = forms.CharField(
        max_length=20, required=False, widget=forms.TextInput(attrs={"placeholder": "Optional"})
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs["placeholder"] = "Password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm password"
        # Drop the auto-generated username field, the model has none.
        self.fields["password1"].help_text = "Use at least 8 characters, not entirely numeric."

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone = self.cleaned_data.get("phone", "")
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Login with e-mail + password (BRD §6)."""

    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autofocus": True})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Incorrect email or password.",
        "inactive": "This account has been deactivated.",
    }


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already in use.")
        return email


class ProfileImageForm(forms.ModelForm):
    class Meta:
        from .models import Profile

        model = Profile
        fields = ["profile_image"]


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "label",
            "full_name",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pin_code",
            "country",
            "address_type",
            "is_default",
        ]
        widgets = {
            "address_line2": forms.TextInput(attrs={"placeholder": "Apartment, suite (optional)"}),
            "is_default": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput,)):
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} form-control".strip()
        self.fields["country"].initial = "India"

    def clean_pin_code(self):
        return self.cleaned_data["pin_code"].strip()

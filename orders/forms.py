"""Checkout forms (BRD §14, §15)."""

from django import forms

from accounts.models import Address

from .models import Order


class CheckoutForm(forms.Form):
    """Collects the delivery address and the payment method in one step.

    The customer either picks a saved address or types a new one; the new
    address fields are only required when no saved address is selected.
    """

    saved_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        widget=forms.RadioSelect,
        empty_label=None,
    )
    payment_method = forms.ChoiceField(
        choices=Order.PaymentMethod.choices,
        widget=forms.RadioSelect,
        initial=Order.PaymentMethod.COD,
    )
    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Delivery instructions (optional)"}),
    )

    # -- one-off address --------------------------------------------------
    new_full_name = forms.CharField(max_length=150, required=False)
    new_phone = forms.CharField(max_length=20, required=False)
    new_address_line1 = forms.CharField(max_length=200, required=False)
    new_address_line2 = forms.CharField(max_length=200, required=False)
    new_city = forms.CharField(max_length=100, required=False)
    new_state = forms.CharField(max_length=100, required=False)
    new_pin_code = forms.CharField(max_length=10, required=False)
    new_country = forms.CharField(max_length=100, required=False, initial="India")
    new_address_type = forms.ChoiceField(
        choices=Address.AddressType.choices,
        required=False,
        initial=Address.AddressType.HOME,
    )
    save_address = forms.BooleanField(
        required=False, label="Save this address to my profile"
    )

    NEW_ADDRESS_FIELDS = (
        "new_full_name",
        "new_phone",
        "new_address_line1",
        "new_city",
        "new_state",
        "new_pin_code",
        "new_country",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if self.user is not None:
            self.fields["saved_address"].queryset = Address.objects.filter(user=self.user)
            self.fields["new_country"].initial = "India"
            self._apply_bootstrap_classes()

    def _apply_bootstrap_classes(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            field.widget.attrs.setdefault("class", "form-control")

    @property
    def has_saved_addresses(self):
        return bool(self.fields["saved_address"].queryset.exists())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("saved_address"):
            return cleaned

        missing = []
        for name in self.NEW_ADDRESS_FIELDS:
            value = (cleaned.get(name) or "").strip()
            if not value:
                missing.append(name.replace("new_", "").replace("_", " "))
        if missing:
            raise forms.ValidationError(
                "Select a saved address or fill in: " + ", ".join(missing) + "."
            )
        return cleaned

    def new_address_data(self):
        return {
            "full_name": self.cleaned_data.get("new_full_name", "").strip(),
            "phone": self.cleaned_data.get("new_phone", "").strip(),
            "address_line1": self.cleaned_data.get("new_address_line1", "").strip(),
            "address_line2": self.cleaned_data.get("new_address_line2", "").strip(),
            "city": self.cleaned_data.get("new_city", "").strip(),
            "state": self.cleaned_data.get("new_state", "").strip(),
            "pin_code": self.cleaned_data.get("new_pin_code", "").strip(),
            "country": self.cleaned_data.get("new_country", "").strip() or "India",
        }


class OrderStatusUpdateForm(forms.Form):
    """Admin status control (BRD §23)."""

    status = forms.ChoiceField(choices=Order.Status.choices)
    note = forms.CharField(required=False, max_length=255)

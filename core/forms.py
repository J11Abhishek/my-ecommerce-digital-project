"""Small forms used by the storefront and the dashboard."""

from django import forms

from orders.models import Order


class OrderStatusForm(forms.Form):
    """Status control on the admin order page (BRD §23)."""

    status = forms.ChoiceField(choices=Order.Status.choices)
    note = forms.CharField(
        required=False, max_length=255, widget=forms.TextInput(attrs={"placeholder": "Note (optional)"})
    )


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

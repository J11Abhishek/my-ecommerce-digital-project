from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "order",
        "method",
        "status",
        "amount",
        "transaction_id",
        "card_last4",
        "created_at",
    ]
    list_filter = ["method", "status", "provider"]
    search_fields = ["order__order_number", "transaction_id", "order__user__email"]
    list_select_related = ["order", "order__user"]
    readonly_fields = ["created_at", "paid_at"]
    date_hierarchy = "created_at"

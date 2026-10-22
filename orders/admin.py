from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .business import ALLOWED_TRANSITIONS
from .models import Order, OrderItem, OrderStatusLog


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "sku", "unit_price", "quantity", "line_total"]
    can_delete = False

    @admin.display(description="Line total")
    def line_total(self, obj):
        return obj.line_total


class OrderStatusLogInline(admin.TabularInline):
    model = OrderStatusLog
    extra = 0
    readonly_fields = ["from_status", "to_status", "note", "changed_by", "created_at"]
    can_delete = False
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "order_number",
        "customer",
        "status_badge",
        "payment_status",
        "total_amount",
        "items_count",
        "placed_at",
    ]
    list_filter = ["status", "payment_status", "payment_method", "placed_at"]
    search_fields = ["order_number", "user__email", "user__first_name", "shipping_full_name", "shipping_city"]
    readonly_fields = [
        "order_number",
        "user",
        "subtotal",
        "shipping_amount",
        "discount_amount",
        "total_amount",
        "shipping_full_name",
        "shipping_phone",
        "shipping_address_line1",
        "shipping_address_line2",
        "shipping_city",
        "shipping_state",
        "shipping_pin_code",
        "shipping_country",
        "notes",
        "placed_at",
        "cancelled_at",
        "cancel_reason",
        "stock_reversed",
    ]
    date_hierarchy = "placed_at"
    inlines = [OrderItemInline, OrderStatusLogInline]
    list_per_page = 25
    fieldsets = (
        ("Order", {"fields": ("order_number", "user", "status", "payment_status", "payment_method", "placed_at")}),
        ("Amounts", {"fields": ("subtotal", "shipping_amount", "discount_amount", "total_amount")}),
        ("Delivery address", {"fields": (
            "shipping_full_name", "shipping_phone", "shipping_address_line1",
            "shipping_address_line2", "shipping_city", "shipping_state",
            "shipping_pin_code", "shipping_country",
        )}),
        ("Other", {"fields": ("notes", "cancel_reason", "cancelled_at", "stock_reversed")}),
    )

    @admin.display(description="Customer", ordering="user__email")
    def customer(self, obj):
        return obj.user.email

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "PENDING": "#b45309",
            "CONFIRMED": "#1d4ed8",
            "PROCESSING": "#1d4ed8",
            "SHIPPED": "#4338ca",
            "DELIVERED": "#15803d",
            "CANCELLED": "#b91c1c",
        }
        color = colors.get(obj.status, "#374151")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>', color, obj.get_status_display()
        )

    @admin.display(description="Items")
    def items_count(self, obj):
        return obj.unique_item_count

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.action(description="Mark selected orders as Confirmed")
    def mark_confirmed(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status in ALLOWED_TRANSITIONS and Order.Status.CONFIRMED in ALLOWED_TRANSITIONS[order.status]:
                order.status = Order.Status.CONFIRMED
                order.save(update_fields=["status", "updated_at"])
                order.status_logs.create(
                    from_status="", to_status=Order.Status.CONFIRMED, note="Bulk action", changed_by=request.user
                )
                count += 1
        self.message_user(request, f"{count} order(s) confirmed.")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "product_name", "sku", "unit_price", "quantity", "line_total"]
    list_filter = ["order__status"]
    search_fields = ["product_name", "sku", "order__order_number"]

    @admin.display(description="Line total")
    def line_total(self, obj):
        return obj.line_total

from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ["product", "quantity", "added_at"]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "session_key", "item_count", "created_at", "updated_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "session_key"]
    inlines = [CartItemInline]

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.unique_items


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ["cart", "product", "quantity", "line_total"]
    list_select_related = ["cart", "product"]

    @admin.display(description="Line total")
    def line_total(self, obj):
        return obj.line_total

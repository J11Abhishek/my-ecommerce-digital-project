from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "product_count", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "image_preview",
        "name",
        "sku",
        "category",
        "price",
        "stock_quantity",
        "stock_state",
        "is_active",
        "is_featured",
    ]
    list_filter = ["is_active", "is_featured", "category", "stock_quantity"]
    search_fields = ["name", "sku", "description", "category__name"]
    list_editable = ["price", "stock_quantity", "is_active", "is_featured"]
    list_select_related = ["category"]
    readonly_fields = ["created_at", "updated_at", "image_preview"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["-created_at"]
    list_per_page = 25
    fieldsets = (
        ("Product", {"fields": ("name", "slug", "sku", "category", "image", "image_preview")}),
        ("Pricing & stock", {"fields": ("price", "stock_quantity")}),
        ("Description", {"fields": ("short_description", "description")}),
        ("Visibility", {"fields": ("is_active", "is_featured")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:44px;width:44px;object-fit:cover;border-radius:6px;">',
                obj.image.url,
            )
        return "-"

    @admin.display(description="Stock")
    def stock_state(self, obj):
        return obj.stock_label

    @admin.action(description="Activate selected products")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} product(s) activated.")

    @admin.action(description="Deactivate selected products")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} product(s) deactivated.")

    @admin.action(description="Restock selected products by +10")
    def restock(self, request, queryset):
        for product in queryset:
            product.stock_quantity += 10
            product.save(update_fields=["stock_quantity", "updated_at"])
        self.message_user(request, f"{queryset.count()} product(s) restocked.")

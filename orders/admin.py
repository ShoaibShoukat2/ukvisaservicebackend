from django.contrib import admin
from .models import Product, Order, OrderItem, SiteConfig


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Branding', {'fields': ('site_name', 'site_tagline')}),
        ('Hero Section', {'fields': ('hero_title', 'hero_subtitle')}),
        ('Hero Stats', {'fields': ('stat_1_value', 'stat_1_label', 'stat_2_value', 'stat_2_label', 'stat_3_value', 'stat_3_label')}),
        ('Contact Info', {'fields': ('contact_email', 'contact_phone')}),
        ('Footer', {'fields': ('footer_text',)}),
    )

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'icon', 'is_popular', 'is_active', 'order']
    list_filter = ['category', 'is_active', 'is_popular']
    list_editable = ['price', 'is_popular', 'is_active', 'order']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['unit_price']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_name', 'customer_email', 'total_amount', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['customer_name', 'customer_email']
    inlines = [OrderItemInline]
    readonly_fields = ['stripe_session_id', 'stripe_payment_intent', 'created_at']

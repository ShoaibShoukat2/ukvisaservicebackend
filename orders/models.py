from django.db import models


class SiteConfig(models.Model):
    """Single-row table for site-wide settings managed from admin."""
    site_name = models.CharField(max_length=100, default='UKVI Services')
    site_tagline = models.CharField(max_length=200, default='Official UK Visa & Immigration Fees')
    hero_title = models.CharField(max_length=200, default='UK Visa & Immigration Fee Payment Made Easy')
    hero_subtitle = models.TextField(default='Pay your UK visa application fees and Immigration Health Surcharge (IHS) securely and instantly.')
    stat_1_value = models.CharField(max_length=20, default='50K+')
    stat_1_label = models.CharField(max_length=50, default='Applications')
    stat_2_value = models.CharField(max_length=20, default='100%')
    stat_2_label = models.CharField(max_length=50, default='Secure')
    stat_3_value = models.CharField(max_length=20, default='24/7')
    stat_3_label = models.CharField(max_length=50, default='Support')
    contact_email = models.EmailField(default='support@ukviservices.co.uk')
    contact_phone = models.CharField(max_length=30, default='+44 20 0000 0000')
    footer_text = models.CharField(max_length=300, default='Not affiliated with the UK Home Office.')

    class Meta:
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configuration'

    def __str__(self):
        return self.site_name


class Product(models.Model):
    CATEGORY_CHOICES = [('visa', 'Visa Fee'), ('ihs', 'IHS Fee')]
    ICON_CHOICES = [
        ('🛂', '🛂 Passport Control'),
        ('✈️', '✈️ Airplane'),
        ('🏥', '🏥 Hospital'),
        ('💳', '💳 Card'),
        ('📋', '📋 Document'),
    ]
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, choices=ICON_CHOICES, default='💳')
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Display order')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name} — £{self.price}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_session_id = models.CharField(max_length=300, blank=True)
    stripe_payment_intent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} — {self.customer_name} — {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

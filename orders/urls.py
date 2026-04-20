from django.urls import path
from . import views

urlpatterns = [
    path('config/', views.SiteConfigView.as_view(), name='site-config'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:order_id>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe-webhook'),
]

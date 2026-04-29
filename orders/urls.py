from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/profile/', views.ProfileView.as_view(), name='profile'),

    # Site & Products
    path('config/', views.SiteConfigView.as_view(), name='site-config'),
    path('products/', views.ProductListView.as_view(), name='products'),

    # Orders
    path('orders/create/', views.OrderCreateView.as_view(), name='order-create'),
    path('orders/my/', views.MyOrdersView.as_view(), name='my-orders'),
    path('orders/<int:order_id>/', views.OrderDetailView.as_view(), name='order-detail'),

    # Stripe
    path('webhook/stripe/', views.stripe_webhook, name='stripe-webhook'),
]

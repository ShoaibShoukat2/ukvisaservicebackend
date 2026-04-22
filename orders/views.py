import logging
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Product, Order, OrderItem, SiteConfig
from .serializers import (
    ProductSerializer, OrderCreateSerializer, OrderSerializer,
    SiteConfigSerializer, RegisterSerializer, CustomTokenSerializer, UserProfileSerializer
)

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


# ─── Auth Views ───────────────────────────────────────────────────────────────
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Registration failed.', 'details': serializer.errors}, status=400)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Account created successfully.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }, status=201)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully.'})
        except Exception:
            return Response({'message': 'Logged out.'})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'error': 'Invalid data.', 'details': serializer.errors}, status=400)
        serializer.save()
        return Response({'message': 'Profile updated.', 'user': serializer.data})


# ─── Site & Product Views ─────────────────────────────────────────────────────
class SiteConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            config, _ = SiteConfig.objects.get_or_create(pk=1)
            return Response(SiteConfigSerializer(config).data)
        except Exception as e:
            logger.error(f"SiteConfig error: {e}")
            return Response({'error': 'Could not load site configuration.'}, status=500)


class ProductListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            products = Product.objects.filter(is_active=True)
            return Response(ProductSerializer(products, many=True).data)
        except Exception as e:
            logger.error(f"ProductList error: {e}")
            return Response({'error': 'Could not load products.'}, status=500)


# ─── Order Views ──────────────────────────────────────────────────────────────
class OrderCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Invalid data.', 'details': serializer.errors}, status=400)

        data = serializer.validated_data
        line_items = []
        total = 0
        order_items_to_create = []

        for item in data['items']:
            try:
                product = Product.objects.get(id=item['product_id'], is_active=True)
            except Product.DoesNotExist:
                return Response({'error': f"Product ID {item['product_id']} not found."}, status=400)
            total += product.price * item['quantity']
            order_items_to_create.append((product, item['quantity'], product.price))
            line_items.append({
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {'name': product.name, 'description': product.description or product.name},
                    'unit_amount': int(product.price * 100),
                },
                'quantity': item['quantity'],
            })

        try:
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer_name=data['customer_name'],
                customer_email=data['customer_email'],
                customer_phone=data['customer_phone'],
                total_amount=total,
                status='pending',
            )
            for product, qty, price in order_items_to_create:
                OrderItem.objects.create(order=order, product=product, quantity=qty, unit_price=price)
        except Exception as e:
            logger.error(f"Order DB error: {e}")
            return Response({'error': 'Failed to create order. Please try again.'}, status=500)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                customer_email=data['customer_email'],
                success_url=f"{settings.FRONTEND_URL}/?payment=success&order_id={order.id}",
                cancel_url=f"{settings.FRONTEND_URL}/?payment=cancelled",
                metadata={'order_id': str(order.id)},
            )
            order.stripe_session_id = session.id
            order.save(update_fields=['stripe_session_id'])
            return Response({'payment_url': session.url, 'order_id': order.id})

        except stripe.error.AuthenticationError:
            return Response({'error': 'Payment gateway not configured. Please contact support.'}, status=503)
        except stripe.error.InvalidRequestError as e:
            order.status = 'failed'; order.save(update_fields=['status'])
            return Response({'error': f'Payment request error: {str(e)}'}, status=400)
        except stripe.error.APIConnectionError:
            order.status = 'failed'; order.save(update_fields=['status'])
            return Response({'error': 'Cannot connect to payment gateway. Please try again.'}, status=503)
        except stripe.error.RateLimitError:
            return Response({'error': 'Too many requests. Please wait and try again.'}, status=429)
        except stripe.error.StripeError as e:
            order.status = 'failed'; order.save(update_fields=['status'])
            logger.error(f"StripeError: {e}")
            return Response({'error': 'Payment processing failed. Please try again.'}, status=500)
        except Exception as e:
            order.status = 'failed'; order.save(update_fields=['status'])
            logger.error(f"Unexpected error: {e}")
            return Response({'error': 'An unexpected error occurred.'}, status=500)


class OrderDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({'error': f'Order #{order_id} not found.'}, status=404)
        except Exception as e:
            logger.error(f"OrderDetail error: {e}")
            return Response({'error': 'Could not retrieve order.'}, status=500)


class MyOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            orders = Order.objects.filter(user=request.user).prefetch_related('items__product')
            return Response(OrderSerializer(orders, many=True).data)
        except Exception as e:
            logger.error(f"MyOrders error: {e}")
            return Response({'error': 'Could not load orders.'}, status=500)


# ─── Stripe Webhook ───────────────────────────────────────────────────────────
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=400)
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session['metadata'].get('order_id')
        if order_id:
            Order.objects.filter(id=order_id).update(
                status='paid',
                stripe_payment_intent=session.get('payment_intent', '')
            )
    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        order_id = session['metadata'].get('order_id')
        if order_id:
            Order.objects.filter(id=order_id, status='pending').update(status='failed')

    return HttpResponse(status=200)

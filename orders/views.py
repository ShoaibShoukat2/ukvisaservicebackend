import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Product, Order, OrderItem, SiteConfig
from .serializers import ProductSerializer, OrderCreateSerializer, OrderSerializer, SiteConfigSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY


class SiteConfigView(APIView):
    def get(self, request):
        config, _ = SiteConfig.objects.get_or_create(pk=1)
        return Response(SiteConfigSerializer(config).data)


class ProductListView(APIView):
    def get(self, request):
        products = Product.objects.filter(is_active=True)
        return Response(ProductSerializer(products, many=True).data)


class OrderCreateView(APIView):
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        items_data = data['items']

        # Validate products & calculate total
        line_items = []
        total = 0
        order_items_to_create = []

        for item in items_data:
            try:
                product = Product.objects.get(id=item['product_id'], is_active=True)
            except Product.DoesNotExist:
                return Response({'error': f"Product {item['product_id']} not found."}, status=400)

            subtotal = product.price * item['quantity']
            total += subtotal
            order_items_to_create.append((product, item['quantity'], product.price))

            line_items.append({
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {'name': product.name, 'description': product.description},
                    'unit_amount': int(product.price * 100),
                },
                'quantity': item['quantity'],
            })

        # Create order
        order = Order.objects.create(
            customer_name=data['customer_name'],
            customer_email=data['customer_email'],
            customer_phone=data['customer_phone'],
            total_amount=total,
            status='pending',
        )
        for product, qty, price in order_items_to_create:
            OrderItem.objects.create(order=order, product=product, quantity=qty, unit_price=price)

        # Create Stripe Checkout Session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                customer_email=data['customer_email'],
                success_url=f"{settings.FRONTEND_URL}/success?order_id={order.id}",
                cancel_url=f"{settings.FRONTEND_URL}/?cancelled=true",
                metadata={'order_id': order.id},
            )
            order.stripe_session_id = session.id
            order.save()
            return Response({'payment_url': session.url, 'order_id': order.id})
        except stripe.error.AuthenticationError:
            # No valid Stripe key — return order_id so frontend can still show success
            return Response({'order_id': order.id, 'warning': 'Stripe not configured. Order saved.'})
        except stripe.error.StripeError as e:
            order.status = 'failed'
            order.save()
            return Response({'error': str(e)}, status=500)


class OrderDetailView(APIView):
    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
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

    return HttpResponse(status=200)

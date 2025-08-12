from rest_framework import mixins
from rest_framework import filters
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status

from decimal import Decimal
from django.db.models import Q
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from products.models import Product
from sales.models import ProductSellingOption, ProductBid, HaggleNegotiation,ProductEventLog
from sales.serializers import (
    ProductBidSerializer,
    ProductSellingOptionSerializer,UserHagglingListSerializer,
    HaggleNegotiationSerializer,PublicAuctionSerializer,
    HaggleOfferSerializer,ProductEventLogSerializer,ProductMinimalSerializer
)
from sales.haggling import make_haggle_offer, cancel_negotiation
from sales.auction import place_proxy_bid, cancel_auction


class IsAuthenticatedAndOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class ProductSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "")
        user = request.user

        if user.user_type != "business":
            return Response([])

        from django.db.models import Q


        products = Product.objects.filter(
            Q(business=user.business_profile) & Q(name__icontains=query)
        ).only("id", "name", "slug")[:10]


        return Response(ProductMinimalSerializer(products, many=True).data)


class ProductSellingOptionViewSet(mixins.CreateModelMixin,
                            viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'
    serializer_class = ProductSellingOptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type != 'business':
            return ProductSellingOption.objects.none()
        return ProductSellingOption.objects.filter(product__business=user.businessprofile)

    def perform_create(self, serializer):
        user = self.request.user

        if user.user_type != 'business':
            raise permissions.PermissionDenied(
                "Only business users can create selling options.")

        product = serializer.validated_data.get('product')
        if product.business != user.businessprofile:
            raise permissions.PermissionDenied(
                "You can only create options for your own products.")

        if hasattr(product, 'selling_option'):
            raise permissions.ValidationError("This product already has a selling option.")

        serializer.save()


class ProductBidViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'
    serializer_class = ProductBidSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProductBid.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        option = serializer.validated_data['product_option']
        amount = serializer.validated_data['max_bid']
        place_proxy_bid(option, self.request.user, Decimal(amount))


class HaggleNegotiationViewSet(viewsets.ModelViewSet):
    serializer_class = HaggleNegotiationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        return HaggleNegotiation.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='offer')
    def make_offer(self, request, slug=None):
        negotiation = self.get_object()
        option = negotiation.product_option
        price = Decimal(request.data.get('offer_price'))
        message = request.data.get('message', '')

        try:
            result = make_haggle_offer(request.user, option, price, message)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, slug=None):
        negotiation = self.get_object()
        try:
            cancel_negotiation(request.user, negotiation)
            return Response({"detail": "Negotiation cancelled."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AuctionAdminViewSet(viewsets.ViewSet):
    lookup_field = 'slug'
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='cancel-auction')
    def cancel_auction_action(self, request, slug=None):
        option = get_object_or_404(ProductSellingOption, slug=slug)
        try:
            cancel_auction(option, request.user)
            return Response({"detail": "Auction cancelled."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SellerEventLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductEventLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        return ProductEventLog.objects.filter(seller=self.request.user)


class PublicAuctionListViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'
    serializer_class = PublicAuctionSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend,
                        filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['product__name', 'min_bid']
    search_fields = ['product__name']
    ordering_fields = ['auction_start_time',
                        'auction_end_time', 'min_bid', 'current_highest_bid']
    ordering = ['auction_end_time']

    def get_queryset(self):
        now_time = now()
        return ProductSellingOption.objects.filter(
            selling_mode='auction',
            auction_start_time__lte=now_time,
            auction_end_time__gte=now_time
        )


class UserHagglingListViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'
    serializer_class = UserHagglingListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ['product_option__product__name']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return HaggleNegotiation.objects.filter(user=self.request.user)

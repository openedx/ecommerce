from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.enterprise.utils import get_enterprise_customers
from rest_framework import filters, generics, serializers, status, viewsets
from oscar.core.loading import get_model
from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.extensions.api.serializers import EnterpriseCouponListSerializer, CouponSerializer
from ecommerce.invoice.models import Invoice
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet

Line = get_model('basket', 'Line')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')


class EnterpriseCustomerViewSet(generics.GenericAPIView):

    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get(self, request):
        site = request.site
        return Response(data={'results': get_enterprise_customers(site)})


class EnterpriseCouponViewSet(CouponViewSet):
    """ Coupon resource. """

    def get_queryset(self):
        invoices = Invoice.objects.filter(business_client__enterprise_customer_uuid__isnull=False)
        orders = Order.objects.filter(id__in=[invoice.order_id for invoice in invoices])
        basket_lines = Line.objects.filter(basket_id__in=[order.basket_id for order in orders])
        return Product.objects.filter(
            product_class__name=COUPON_PRODUCT_CLASS_NAME,
            stockrecords__partner=self.request.site.siteconfiguration.partner,
            id__in=[line.product_id for line in basket_lines],
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return EnterpriseCouponListSerializer
        return CouponSerializer

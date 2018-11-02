from __future__ import unicode_literals

from ecommerce.enterprise.utils import get_enterprise_customers
from ecommerce.extensions.api.serializers import EnterpriseCouponListSerializer, CouponSerializer
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from oscar.core.loading import get_model
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.core.models import BusinessClient
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import (
    create_coupon_product_and_stockrecord, attach_vouchers_to_coupon_product
)
from ecommerce.extensions.voucher.utils import create_enterprise_vouchers, update_voucher_with_enterprise_offer
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.invoice.models import Invoice

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

DEPRECATED_COUPON_CATEGORIES = ['Bulk Enrollment']

Line = get_model('basket', 'Line')


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

    def create_coupon_product(self, cleaned_voucher_data):
        coupon_product = create_coupon_product_and_stockrecord(
            cleaned_voucher_data['title'],
            cleaned_voucher_data['category'],
            cleaned_voucher_data['partner'],
            cleaned_voucher_data['price']
        )

        try:
            vouchers = create_enterprise_vouchers(
                voucher_type=cleaned_voucher_data['voucher_type'],
                quantity=cleaned_voucher_data['quantity'],
                coupon_id=coupon_product.id,
                benefit_type=cleaned_voucher_data['benefit_type'],
                benefit_value=cleaned_voucher_data['benefit_value'],
                enterprise_customer=cleaned_voucher_data['enterprise_customer'],
                enterprise_customer_catalog=cleaned_voucher_data['enterprise_customer_catalog'],
                max_uses=cleaned_voucher_data['max_uses'],
                email_domains=cleaned_voucher_data['email_domains'],
                site=self.request.site,
                end_datetime=cleaned_voucher_data['end_datetime'],
                start_datetime=cleaned_voucher_data['start_datetime'],
                code=cleaned_voucher_data['code'],
                name=cleaned_voucher_data['title']
            )
        except IntegrityError:
            logger.exception('Failed to create vouchers for [%s] coupon.', coupon_product.title)
            raise

        attach_vouchers_to_coupon_product(coupon_product, vouchers, cleaned_voucher_data['note'])
        return coupon_product

    def update_range_data(self, request_data, vouchers):
        pass

    def update_offer_data(self, request_data, vouchers, site):
        """
        Remove all offers from the vouchers and add a new offer
        Arguments:
            coupon (Product): Coupon product associated with vouchers
            vouchers (ManyRelatedManager): Vouchers associated with the coupon to be updated
            site (Site): The Site associated with this offer
            benefit_value (Decimal): Benefit value associated with a new offer
            program_uuid (str): Program UUID
            enterprise_customer (str): Enterprise Customer UUID
            enterprise_catalog (str): Enterprise Catalog UUID
        """
        benefit_value = request_data.get('benefit_value')
        enterprise_customer = request_data.get('enterprise_customer', {}).get('id', None)
        enterprise_catalog = request_data.get('enterprise_customer_catalog') or None
        max_uses = request_data.get('max_uses')
        email_domains = request_data.get('email_domains')

        # Validate max_uses
        if max_uses is not None:
            if vouchers.first().usage == Voucher.SINGLE_USE:
                log_message_and_raise_validation_error(
                    'Failed to update Coupon. '
                    'max_global_applications field cannot be set for voucher type [{voucher_type}].'.format(
                        voucher_type=Voucher.SINGLE_USE
                    ))
            try:
                max_uses = int(max_uses)
                if max_uses < 1:
                    raise ValueError
            except ValueError:
                raise ValidationError('max_global_applications field must be a positive number.')

        for voucher in vouchers.all():
            updated_enterprise_offer = update_voucher_with_enterprise_offer(
                offer=voucher.enterprise_offer,
                benefit_value=benefit_value,
                max_uses=max_uses,
                enterprise_customer=enterprise_customer,
                enterprise_catalog=enterprise_catalog,
                email_domains=email_domains,
                site=site,
            )
            voucher.offers.clear()
            voucher.offers.add(updated_enterprise_offer)


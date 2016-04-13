from __future__ import unicode_literals

import logging

import dateutil.parser

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from oscar.core.loading import get_model
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.models import BusinessClient
from ecommerce.coupons import api as coupons_api
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.serializers import CategorySerializer, CouponSerializer
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
ProductCategory = get_model('catalogue', 'ProductCategory')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class CouponViewSet(EdxOrderPlacementMixin, viewsets.ModelViewSet):
    """Endpoint for creating coupons.

    Creates a new coupon product, adds it to a basket and creates a
    new order from that basket.
    """
    queryset = Product.objects.filter(product_class__name='Coupon')
    serializer_class = CouponSerializer
    permission_classes = (IsAuthenticated, IsAdminUser)
    filter_backends = (filters.DjangoFilterBackend, )
    filter_class = ProductFilter

    def create(self, request, *args, **kwargs):
        """Adds coupon to the user's basket.

        Expects request array to contain all the necessary data (listed out below).
        This information is then used to create a coupon product, add to a
        basket and create an order from it.

        Arguments:
            request (HttpRequest): With parameters title, client_username,
            stock_record_ids, start_date, end_date, code, benefit_type, benefit_value,
            voucher_type, quantity, price, category and note in the body.

        Returns:
            200 if the order was created successfully; the basket ID is included in the response
                body along with the order ID and payment information.
            401 if an unauthenticated request is denied permission to access the endpoint.
            429 if the client has made requests at a rate exceeding that allowed by the configured rate limit.
            500 if an error occurs when attempting to create a coupon.
        """
        with transaction.atomic():
            title = request.data[AC.KEYS.TITLE]
            client_username = request.data[AC.KEYS.CLIENT_USERNAME]
            stock_record_ids = request.data[AC.KEYS.STOCK_RECORD_IDS]
            start_date = dateutil.parser.parse(request.data[AC.KEYS.START_DATE])
            end_date = dateutil.parser.parse(request.data[AC.KEYS.END_DATE])
            code = request.data[AC.KEYS.CODE]
            benefit_type = request.data[AC.KEYS.BENEFIT_TYPE]
            benefit_value = request.data[AC.KEYS.BENEFIT_VALUE]
            voucher_type = request.data[AC.KEYS.VOUCHER_TYPE]
            quantity = request.data[AC.KEYS.QUANTITY]
            price = request.data[AC.KEYS.PRICE]
            partner = request.site.siteconfiguration.partner
            categories = Category.objects.filter(id__in=request.data['category_ids'])
            client, __ = BusinessClient.objects.get_or_create(name=client_username)
            note = request.data.get('note', None)

            # We currently do not support multi-use voucher types.
            if voucher_type == Voucher.MULTI_USE:
                raise NotImplementedError('Multi-use voucher types are not supported')

            # When a black-listed course mode is received raise an exception.
            # Audit modes do not have a certificate type and therefor will raise
            # an AttributeError exception.
            seats = Product.objects.filter(stockrecords__id__in=stock_record_ids)
            for seat in seats:
                try:
                    if seat.attr.certificate_type in settings.BLACK_LIST_COUPON_COURSE_MODES:
                        raise Exception('Course mode not supported')
                except AttributeError:
                    raise Exception('Course mode not supported')

            # Create the coupon product and the specified number of vouchers
            coupon_product = coupons_api.create_or_update_coupon_product(
                title=title,
                price=price,
                stock_record_ids=stock_record_ids,
                partner=partner,
                categories=categories,
                note=note,
                create_vouchers=True,
                benefit_type=benefit_type,
                benefit_value=benefit_value,
                start_date=start_date,
                end_date=end_date,
                code=code,
                quantity=quantity,
                voucher_type=voucher_type
            )

            basket = prepare_basket(request, coupon_product)

            # Create an order now since payment is handled out of band via an invoice.
            response_data = self.create_order_for_invoice(basket, coupon_id=coupon_product.id, client=client)

            return Response(response_data, status=status.HTTP_200_OK)

    def create_order_for_invoice(self, basket, coupon_id, client):
        """Creates an order from the basket and invokes the invoice payment processor."""
        order_metadata = data_api.get_order_metadata(basket)

        response_data = {
            AC.KEYS.COUPON_ID: coupon_id,
            AC.KEYS.BASKET_ID: basket.id,
            AC.KEYS.ORDER: None,
            AC.KEYS.PAYMENT_DATA: None,
        }
        basket.freeze()

        order = self.handle_order_placement(
            order_number=order_metadata[AC.KEYS.ORDER_NUMBER],
            user=basket.owner,
            basket=basket,
            shipping_address=None,
            shipping_method=order_metadata[AC.KEYS.SHIPPING_METHOD],
            shipping_charge=order_metadata[AC.KEYS.SHIPPING_CHARGE],
            billing_address=None,
            order_total=order_metadata[AC.KEYS.ORDER_TOTAL]
        )

        # Invoice payment processor invocation.
        payment_processor = InvoicePayment
        payment_processor().handle_processor_response(response={}, order=order, business_client=client)
        response_data[AC.KEYS.PAYMENT_DATA] = {
            AC.KEYS.PAYMENT_PROCESSOR_NAME: 'Invoice'
        }

        response_data[AC.KEYS.ORDER] = order.id
        logger.info(
            'Created new order number [%s] from basket [%d]',
            order_metadata[AC.KEYS.ORDER_NUMBER],
            basket.id
        )

        return response_data

    def update(self, request, *args, **kwargs):
        """Update start and end dates of all vouchers associated with the coupon."""
        super(CouponViewSet, self).update(request, *args, **kwargs)
        coupon = self.get_object()

        start_datetime = request.data.get(AC.KEYS.START_DATE, '')
        if start_datetime:
            coupon.attr.coupon_vouchers.vouchers.all().update(start_datetime=start_datetime)

        end_datetime = request.data.get(AC.KEYS.END_DATE, '')
        if end_datetime:
            coupon.attr.coupon_vouchers.vouchers.all().update(end_datetime=end_datetime)

        serializer = self.get_serializer(coupon)
        return Response(serializer.data)

    def destroy(self, request, pk):  # pylint: disable=unused-argument
        try:
            coupon = get_object_or_404(Product, pk=pk)
            self.perform_destroy(coupon)
        except Http404:
            return Response(status=404)
        return Response(status=204)

    def perform_destroy(self, coupon):
        Voucher.objects.filter(coupon_vouchers__coupon=coupon).delete()
        StockRecord.objects.filter(product=coupon).delete()
        coupon.delete()


class CouponCategoriesListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        parent_category = Category.objects.get(slug='coupons')
        return parent_category.get_children()

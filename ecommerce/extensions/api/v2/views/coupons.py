from __future__ import unicode_literals

import dateutil.parser
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.decorators import method_decorator
from oscar.core.loading import get_model
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ecommerce.core.models import Client
from ecommerce.extensions.api import serializers, data as data_api
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet
from ecommerce.extensions.catalogue.utils import generate_sku, get_or_create_catalog, generate_upc
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import create_vouchers

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


class CouponOrderCreateView(generics.CreateAPIView, EdxOrderPlacementMixin, NonDestroyableModelViewSet):
    """Endpoint for creating coupon orders.

    Creates a new coupon product, adds it to a basket and creates a
    new order from that basket.
    """
    queryset = Product.objects.filter(
        product_class=ProductClass.objects.get(name='Coupon')
    )
    permission_classes = (IsAuthenticated, IsAdminUser)
    serializer_class = serializers.CouponSerializer

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(CouponOrderCreateView, self).dispatch(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Adds coupon to the user's basket.

        Expects request array to contain all the necessary data (listed out below).
        This information is then used to create a coupon product, add to a
        basket and create an order from it.

        Arguments:
            request (HttpRequest): With parameters title, client_username,
            stock_record_ids, start_date, end_date, code, benefit_type,
            benefit_value, voucher_type, quantity and price in the body.

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

            client, __ = Client.objects.get_or_create(username=client_username)

            coupon_catalog = get_or_create_catalog(
                name='Coupon',  # Catalog classifier.
                partner=partner,
                stock_record_ids=stock_record_ids
            )

            data = {
                'partner': partner,
                'title': title,
                'benefit_type': benefit_type,
                'benefit_value': benefit_value,
                'catalog': coupon_catalog,
                'end_date': end_date,
                'code': code,
                'quantity': quantity,
                'start_date': start_date,
                'voucher_type': voucher_type
            }

            coupon_product = self.create_coupon_product(title, price, data)

            basket = self.add_product_to_basket(
                product=coupon_product,
                client=client,
                site=request.site
            )

            response_data = self.create_order_for_invoice(basket)

            return Response(response_data, status=status.HTTP_200_OK)

    def create_coupon_product(self, title, price, data):
        """Creates a coupon product and a stock record for it.

        Arguments:
            title (string): The name of the coupon.
            price (integer): The price of the coupon(s).
            data (dict): Contains data needed to create vouchers,SKU and UPC:
                - partner (User)
                - benefit_type (string)
                - benefit_value (integer)
                - catalog (Catalog)
                - end_date (Datetime)
                - code (string)
                - quantity (integer)
                - start_date (Datetime)
                - voucher_type (string)

        Returns:
            A coupon product object.
        """

        upc = generate_upc(
            title=title,
            catalog=data['catalog'],
            partner=data['partner']
        )
        product_class = ProductClass.objects.get(slug='coupon')
        coupon_product, created = Product.objects.get_or_create(
            product_class=product_class,
            upc=upc
        )

        sku = generate_sku(
            product=coupon_product,
            partner=data['partner'],
            catalog=data['catalog'],
        )

        if created:
            coupon_product.title = title

            stock_record = StockRecord.objects.create(
                product=coupon_product,
                partner=data['partner'],
                partner_sku=sku
            )
            stock_record.price_currency = 'USD'
            stock_record.price_excl_tax = price
            stock_record.save()
        else:
            stock_record = StockRecord.objects.get(
                partner=data['partner'],
                partner_sku=sku
            )
            stock_record.price_excl_tax = price
            stock_record.save()

        # Product validation.
        try:
            coupon_product.clean()
        except ValidationError as ex:
            logger.exception(
                'Failed to validate [%s] coupon.',
                coupon_product.title
            )
            raise ValidationError(ex)

        coupon_product.save()

        try:
            create_vouchers(
                name=title,
                benefit_type=data['benefit_type'],
                benefit_value=Decimal(data['benefit_value']),
                catalog=data['catalog'],
                coupon=coupon_product,
                end_date=data['end_date'],
                code=data['code'],
                quantity=int(data['quantity']),
                start_date=data['start_date'],
                voucher_type=data['voucher_type']
            )
        except IntegrityError as ex:
            logger.exception(
                'Failed to create vouchers for [%s] coupon.',
                coupon_product.title
            )
            raise IntegrityError(ex)  # pylint: disable=nonstandard-exception

        coupon_vouchers = CouponVouchers.objects.get(coupon=coupon_product)

        coupon_product.attr.coupon_vouchers = coupon_vouchers
        coupon_product.save()

        return coupon_product

    def add_product_to_basket(self, product, client, site):
        """Adds the coupon product to the user's basket."""
        basket = Basket.get_basket(client, site)
        basket.add_product(product)
        logger.info(
            'Added product with SKU [%s] to basket [%d]',
            product.stockrecords.first().partner_sku, basket.id
        )
        return basket

    def create_order_for_invoice(self, basket):
        """Creates an order from the basket and invokes the invoice payment processor."""
        order_metadata = data_api.get_order_metadata(basket)

        response_data = {
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

        response_data[AC.KEYS.ORDER] = order.id
        logger.info(
            'Created new order number [%s] from basket [%d]',
            order_metadata[AC.KEYS.ORDER_NUMBER],
            basket.id
        )

        # Invoice payment processor invocation.
        payment_processor = InvoicePayment
        payment_processor().handle_processor_response(response={}, basket=basket)
        response_data[AC.KEYS.PAYMENT_DATA] = {
            AC.KEYS.PAYMENT_PROCESSOR_NAME: 'Invoice'
        }

        return response_data

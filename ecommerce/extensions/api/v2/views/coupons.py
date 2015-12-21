from __future__ import unicode_literals

import logging
from decimal import Decimal
import dateutil.parser

from django.db import transaction
from django.db.utils import IntegrityError
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ecommerce.core.models import Client
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.serializers import CouponSerializer
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet
from ecommerce.extensions.catalogue.utils import generate_sku, get_or_create_catalog, generate_coupon_slug
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import create_vouchers

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
ProductCategory = get_model('catalogue', 'ProductCategory')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


class CouponViewSet(EdxOrderPlacementMixin, NonDestroyableModelViewSet):
    """Endpoint for creating coupons.

    Creates a new coupon product, adds it to a basket and creates a
    new order from that basket.
    """
    queryset = Product.objects.filter(product_class__name='Coupon')
    serializer_class = CouponSerializer
    permission_classes = (IsAuthenticated, IsAdminUser)

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
            category = request.data[AC.KEYS.CATEGORY] or 'Other'

            client, __ = Client.objects.get_or_create(username=client_username)

            stock_records_string = ' '.join(str(id) for id in stock_record_ids)

            coupon_catalog, __ = get_or_create_catalog(
                name='Catalog for stock records: {}'.format(stock_records_string),
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
                'voucher_type': voucher_type,
                'category': category
            }

            coupon_product = self.create_coupon_product(title, price, data)

            basket = self.add_product_to_basket(
                product=coupon_product,
                client=client,
                site=request.site,
                partner=partner
            )

            # Create an order now since payment is handled out of band via an invoice.
            response_data = self.create_order_for_invoice(basket, coupon_id=coupon_product.id)

            return Response(response_data, status=status.HTTP_200_OK)

    def create_coupon_product(self, title, price, data):
        """Creates a coupon product and a stock record for it.

        Arguments:
            title (str): The name of the coupon.
            price (int): The price of the coupon(s).
            data (dict): Contains data needed to create vouchers,SKU and UPC:
                - partner (User)
                - benefit_type (str)
                - benefit_value (int)
                - catalog (Catalog)
                - end_date (Datetime)
                - code (str)
                - quantity (int)
                - start_date (Datetime)
                - voucher_type (str)
                - category (str)

        Returns:
            A coupon product object.

        Raises:
            IntegrityError: An error occured when create_vouchers method returns
                            an IntegrityError exception
            ValidationError: An error occured clean() validation method returns
                             a ValidationError exception
        """
        coupon_slug = generate_coupon_slug(title=title, catalog=data['catalog'], partner=data['partner'])

        product_class = ProductClass.objects.get(slug='coupon')
        coupon_product, __ = Product.objects.get_or_create(
            title=title,
            product_class=product_class,
            slug=coupon_slug
        )

        # Vouchers are created during order and not fulfillment like usual
        # because we want vouchers to be part of the line in the order.
        try:
            create_vouchers(
                name=title,
                benefit_type=data['benefit_type'],
                benefit_value=Decimal(data['benefit_value']),
                catalog=data['catalog'],
                coupon=coupon_product,
                end_datetime=data['end_date'],
                code=data['code'] or None,
                quantity=int(data['quantity']),
                start_datetime=data['start_date'],
                voucher_type=data['voucher_type']
            )
        except IntegrityError as ex:
            logger.exception('Failed to create vouchers for [%s] coupon.', coupon_product.title)
            raise IntegrityError(ex)  # pylint: disable=nonstandard-exception

        coupon_vouchers = CouponVouchers.objects.get(coupon=coupon_product)

        coupon_product.attr.coupon_vouchers = coupon_vouchers
        category = create_from_breadcrumbs(data['category'])
        ProductCategory.objects.get_or_create(category=category, product=coupon_product)

        coupon_product.save()

        sku = generate_sku(
            product=coupon_product,
            partner=data['partner'],
            catalog=data['catalog'],
        )

        stock_record, __ = StockRecord.objects.get_or_create(
            product=coupon_product,
            partner=data['partner'],
            partner_sku=sku
        )
        stock_record.price_currency = 'USD'
        stock_record.price_excl_tax = price
        stock_record.save()

        return coupon_product

    def add_product_to_basket(self, product, client, site, partner):
        """Adds the coupon product to the user's basket."""
        basket = Basket.get_basket(client, site)
        basket.add_product(product)
        logger.info(
            'Added product with SKU [%s] to basket [%d]',
            product.stockrecords.filter(partner=partner).first().partner_sku,
            basket.id
        )
        return basket

    def create_order_for_invoice(self, basket, coupon_id):
        """Creates an order from the basket and invokes the invoice payment processor."""
        order_metadata = data_api.get_order_metadata(basket)

        response_data = {
            AC.KEYS.COUPON_ID: coupon_id,
            AC.KEYS.BASKET_ID: basket.id,
            AC.KEYS.ORDER: None,
            AC.KEYS.PAYMENT_DATA: None,
        }
        basket.freeze()

        # Invoice payment processor invocation.
        payment_processor = InvoicePayment
        payment_processor().handle_processor_response(response={}, basket=basket)
        response_data[AC.KEYS.PAYMENT_DATA] = {
            AC.KEYS.PAYMENT_PROCESSOR_NAME: 'Invoice'
        }

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

        return response_data

    def update(self, request, *args, **kwargs):
        """Update start and end dates of all vouchers associated with the coupon."""
        super(CouponViewSet, self).update(request, *args, **kwargs)
        coupon = self.get_object()

        start_datetime = request.data.get('start_datetime', '')
        if start_datetime:
            coupon.attr.coupon_vouchers.vouchers.all().update(start_datetime=start_datetime)

        end_datetime = request.data.get('end_datetime', '')
        if end_datetime:
            coupon.attr.coupon_vouchers.vouchers.all().update(end_datetime=end_datetime)

        serializer = self.get_serializer(coupon)
        return Response(serializer.data)

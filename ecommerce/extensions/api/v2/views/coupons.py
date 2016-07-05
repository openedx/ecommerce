from __future__ import unicode_literals

import logging
from decimal import Decimal

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
from ecommerce.coupons.utils import prepare_course_seat_types
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.serializers import CategorySerializer, CouponSerializer, CouponListSerializer
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import generate_sku, get_or_create_catalog
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import create_vouchers, update_voucher_offer
from ecommerce.invoice.models import Invoice

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
Range = Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class CouponViewSet(EdxOrderPlacementMixin, viewsets.ModelViewSet):
    """ Coupon resource. """
    queryset = Product.objects.filter(product_class__name='Coupon')
    permission_classes = (IsAuthenticated, IsAdminUser)
    filter_backends = (filters.DjangoFilterBackend, )
    filter_class = ProductFilter

    def get_serializer_class(self):
        if self.action == 'list':
            return CouponListSerializer
        return CouponSerializer

    def retrieve_invoice_data(self, request_data):
        """ Retrieve the invoice information from the request data. """
        invoice_data = {}

        for field in Invoice.UPDATEABLE_INVOICE_FIELDS:
            self.create_update_data_dict(
                request_data=request_data,
                request_data_key=field,
                update_dict=invoice_data,
                update_dict_key=field.replace('invoice_', '')
            )

        return invoice_data

    def create(self, request, *args, **kwargs):
        """Adds coupon to the user's basket.

        Expects request array to contain all the necessary data (listed out below).
        This information is then used to create a coupon product, add to a
        basket and create an order from it.

        Arguments:
            request (HttpRequest): With parameters title, client,
            stock_record_ids, start_date, end_date, code, benefit_type, benefit_value,
            voucher_type, quantity, price, category, note and invoice data in the body.

        Returns:
            200 if the order was created successfully; the basket ID is included in the response
                body along with the order ID and payment information.
            400 if a custom code is received that already exists,
                if a course mode is selected that is not supported.
            401 if an unauthenticated request is denied permission to access the endpoint.
            429 if the client has made requests at a rate exceeding that allowed by the configured rate limit.
            500 if an error occurs when attempting to create a coupon.
        """
        with transaction.atomic():
            title = request.data.get('title')
            client_username = request.data.get('client')
            stock_record_ids = request.data.get('stock_record_ids')
            start_date = dateutil.parser.parse(request.data.get('start_date'))
            end_date = dateutil.parser.parse(request.data.get('end_date'))
            code = request.data.get('code')
            benefit_type = request.data.get('benefit_type')
            benefit_value = request.data.get('benefit_value')
            voucher_type = request.data.get('voucher_type')
            quantity = request.data.get('quantity')
            price = request.data.get('price')
            partner = request.site.siteconfiguration.partner
            categories = Category.objects.filter(id__in=request.data.get('category_ids'))
            client, __ = BusinessClient.objects.get_or_create(name=client_username)
            note = request.data.get('note')
            max_uses = request.data.get('max_uses')
            catalog_query = request.data.get('catalog_query')
            course_seat_types = request.data.get('course_seat_types')

            if code:
                try:
                    Voucher.objects.get(code=code)
                    return Response(
                        'A coupon with code {code} already exists.'.format(code=code),
                        status=status.HTTP_400_BAD_REQUEST
                    )
                except Voucher.DoesNotExist:
                    pass

            invoice_data = self.retrieve_invoice_data(request.data)

            if course_seat_types:
                course_seat_types = prepare_course_seat_types(course_seat_types)

            # Maximum number of uses can be set for each voucher type and disturb
            # the predefined behaviours of the different voucher types. Therefor
            # here we enforce that the max_uses variable can't be used for SINGLE_USE
            # voucher types.
            if max_uses and voucher_type != Voucher.SINGLE_USE:
                max_uses = int(max_uses)
            else:
                max_uses = None

            # When a black-listed course mode is received raise an exception.
            # Audit modes do not have a certificate type and therefore will raise
            # an AttributeError exception.
            if stock_record_ids:
                seats = Product.objects.filter(stockrecords__id__in=stock_record_ids)
                for seat in seats:
                    try:
                        if seat.attr.certificate_type in settings.BLACK_LIST_COUPON_COURSE_MODES:
                            return Response('Course mode not supported', status=status.HTTP_400_BAD_REQUEST)
                    except AttributeError:
                        return Response('Course mode not supported', status=status.HTTP_400_BAD_REQUEST)

                stock_records_string = ' '.join(str(id) for id in stock_record_ids)
                coupon_catalog, __ = get_or_create_catalog(
                    name='Catalog for stock records: {}'.format(stock_records_string),
                    partner=partner,
                    stock_record_ids=stock_record_ids
                )
            else:
                coupon_catalog = None

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
                'categories': categories,
                'note': note,
                'max_uses': max_uses,
                'catalog_query': catalog_query,
                'course_seat_types': course_seat_types
            }

            coupon_product = self.create_coupon_product(title, price, data)

            basket = prepare_basket(request, coupon_product)

            # Create an order now since payment is handled out of band via an invoice.
            response_data = self.create_order_for_invoice(
                basket, coupon_id=coupon_product.id, client=client, invoice_data=invoice_data
            )

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
                - categories (list of Category objects)
                - note (str)
                - max_uses (int)
                - catalog_query (str)
                - course_seat_types (str)

        Returns:
            A coupon product object.
        """

        product_class = ProductClass.objects.get(slug='coupon')
        coupon_product = Product.objects.create(title=title, product_class=product_class)

        self.assign_categories_to_coupon(coupon=coupon_product, categories=data['categories'])

        # Vouchers are created during order and not fulfillment like usual
        # because we want vouchers to be part of the line in the order.
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
            voucher_type=data['voucher_type'],
            max_uses=data['max_uses'],
            catalog_query=data['catalog_query'],
            course_seat_types=data['course_seat_types']
        )

        coupon_vouchers = CouponVouchers.objects.get(coupon=coupon_product)

        coupon_product.attr.coupon_vouchers = coupon_vouchers
        coupon_product.attr.note = data['note']
        coupon_product.save()

        sku = generate_sku(product=coupon_product, partner=data['partner'])
        StockRecord.objects.update_or_create(
            product=coupon_product,
            partner=data['partner'],
            partner_sku=sku,
            defaults={
                'price_currency': 'USD',
                'price_excl_tax': price
            }
        )

        return coupon_product

    def assign_categories_to_coupon(self, coupon, categories):
        """
        Assigns categories to a coupon.

        Arguments:
            coupon (Product): Coupon product
            categories (list): List of Category instances
        """
        for category in categories:
            ProductCategory.objects.get_or_create(product=coupon, category=category)

    def create_order_for_invoice(self, basket, coupon_id, client, invoice_data=None):
        """Creates an order from the basket and invokes the invoice payment processor."""
        order_metadata = data_api.get_order_metadata(basket)

        response_data = {
            'coupon_id': coupon_id,
            'id': basket.id,
            'order': None,
            'payment_data': None,
        }
        basket.freeze()

        order = self.handle_order_placement(
            order_number=order_metadata['number'],
            user=basket.owner,
            basket=basket,
            shipping_address=None,
            shipping_method=order_metadata['shipping_method'],
            shipping_charge=order_metadata['shipping_charge'],
            billing_address=None,
            order_total=order_metadata['total']
        )

        # Invoice payment processor invocation.
        payment_processor = InvoicePayment
        payment_processor().handle_processor_response(
            response={}, order=order, business_client=client, invoice_data=invoice_data
        )
        response_data['payment_data'] = {
            'payment_processor_name': 'Invoice'
        }

        response_data['order'] = order.id
        logger.info(
            'Created new order number [%s] from basket [%d]',
            order_metadata['number'],
            basket.id
        )

        return response_data

    def update(self, request, *args, **kwargs):
        """Update start and end dates of all vouchers associated with the coupon."""
        super(CouponViewSet, self).update(request, *args, **kwargs)

        coupon = self.get_object()
        vouchers = coupon.attr.coupon_vouchers.vouchers
        baskets = Basket.objects.filter(lines__product_id=coupon.id, status=Basket.SUBMITTED)
        data = {}

        for field in CouponVouchers.UPDATEABLE_VOUCHER_FIELDS:
            self.create_update_data_dict(
                request_data=request.data,
                request_data_key=field['request_data_key'],
                update_dict=data,
                update_dict_key=field['attribute']
            )

        if data:
            vouchers.all().update(**data)

        range_data = {}

        for field in Range.UPDATABLE_RANGE_FIELDS:
            self.create_update_data_dict(
                request_data=request.data,
                request_data_key=field,
                update_dict=range_data,
                update_dict_key=field
            )

        if range_data:
            voucher_range = vouchers.first().offers.first().benefit.range
            Range.objects.filter(id=voucher_range.id).update(**range_data)

        benefit_value = request.data.get('benefit_value')
        if benefit_value:
            self.update_coupon_benefit_value(benefit_value=benefit_value, vouchers=vouchers, coupon=coupon)

        category_ids = request.data.get('category_ids')
        if category_ids:
            self.update_coupon_category(category_ids=category_ids, coupon=coupon)

        client_username = request.data.get('client')
        if client_username:
            self.update_coupon_client(baskets=baskets, client_username=client_username)

        coupon_price = request.data.get('price')
        if coupon_price:
            StockRecord.objects.filter(product=coupon).update(price_excl_tax=coupon_price)

        note = request.data.get('note')
        if note is not None:
            coupon.attr.note = note
            coupon.save()

        self.update_invoice_data(coupon, request.data)

        serializer = self.get_serializer(coupon)
        return Response(serializer.data)

    def create_update_data_dict(self, request_data, request_data_key, update_dict, update_dict_key):
        """
        Adds the value from request data to the update data dictionary
        Arguments:
            request_data (QueryDict): Request data
            request_data_key (str): Request data dictionary key
            update_dict (dict): Dictionary containing the coupon update data
            update_dict_key (str): Update data dictionary key
        """
        if request_data_key in request_data:
            value = request_data.get(request_data_key)
            update_dict[update_dict_key] = prepare_course_seat_types(value) \
                if update_dict_key == 'course_seat_types' else value

    def update_coupon_benefit_value(self, benefit_value, coupon, vouchers):
        """
        Remove all offers from the vouchers and add a new offer
        Arguments:
            benefit_value (Decimal): Benefit value associated with a new offer
            coupon (Product): Coupon product associated with vouchers
            vouchers (ManyRelatedManager): Vouchers associated with the coupon to be updated
            coupon (Product): Coupon product associated with vouchers
        """
        voucher_offers = vouchers.first().offers
        voucher_offer = voucher_offers.first()

        new_offer = update_voucher_offer(
            offer=voucher_offer,
            benefit_value=benefit_value,
            benefit_type=voucher_offer.benefit.type,
            coupon=coupon,
            max_uses=voucher_offer.max_global_applications
        )
        for voucher in vouchers.all():
            voucher.offers.clear()
            voucher.offers.add(new_offer)

    def update_coupon_category(self, category_ids, coupon):
        """
        Remove categories currently assigned to a coupon and assigned new categories
        Arguments:
            category_ids (list): List of category IDs
            coupon (Product): Coupon product to be updated
        """
        new_categories = Category.objects.filter(id__in=category_ids)

        ProductCategory.objects.filter(product=coupon).exclude(category__in=new_categories).delete()

        self.assign_categories_to_coupon(coupon=coupon, categories=new_categories)

    def update_coupon_client(self, baskets, client_username):
        """
        Update Invoice client for new coupons.
        Arguments:
            baskets (QuerySet): Baskets associated with the coupons
            client_username (str): Client username
        """
        client, __ = BusinessClient.objects.get_or_create(name=client_username)
        Invoice.objects.filter(order__basket=baskets.first()).update(business_client=client)

    def update_invoice_data(self, coupon, data):
        """
        Update the invoice data.

        Arguments:
            coupon (Product): The coupon product with which the invoice is retrieved.
            data (dict): The request's data from which the invoice data is retrieved
                         and used for the updated.
        """
        invoice_data = self.retrieve_invoice_data(data)

        if invoice_data:
            Invoice.objects.filter(order__basket__lines__product=coupon).update(**invoice_data)

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

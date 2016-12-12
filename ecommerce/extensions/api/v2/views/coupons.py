from __future__ import unicode_literals

import logging

import dateutil.parser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from oscar.core.loading import get_model
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.models import BusinessClient
from ecommerce.coupons.utils import prepare_course_seat_types
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.serializers import CategorySerializer, CouponSerializer, CouponListSerializer
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import create_coupon_product, get_or_create_catalog
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import update_voucher_offer
from ecommerce.invoice.models import Invoice

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
Range = get_model('offer', 'Range')
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
        category_data = request.data.get('category')
        code = request.data.get('code')
        course_seat_types = request.data.get('course_seat_types')
        max_uses = request.data.get('max_uses')
        partner = request.site.siteconfiguration.partner
        stock_record_ids = request.data.get('stock_record_ids')
        voucher_type = request.data.get('voucher_type')

        try:
            with transaction.atomic():
                if code:
                    try:
                        Voucher.objects.get(code=code)
                        return Response(
                            'A coupon with code {code} already exists.'.format(code=code),
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    except Voucher.DoesNotExist:
                        pass

                if course_seat_types:
                    course_seat_types = prepare_course_seat_types(course_seat_types)

                try:
                    category = Category.objects.get(name=category_data['name'])
                except Category.DoesNotExist:
                    return Response(
                        'Category {category_name} not found.'.format(category_name=category_data['name']),
                        status=status.HTTP_404_NOT_FOUND
                    )
                except KeyError:
                    return Response('Invalid Coupon Category data.', status=status.HTTP_400_BAD_REQUEST)

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

                coupon_product = create_coupon_product(
                    benefit_type=request.data.get('benefit_type'),
                    benefit_value=request.data.get('benefit_value'),
                    catalog=coupon_catalog,
                    catalog_query=request.data.get('catalog_query'),
                    category=category,
                    code=code,
                    course_seat_types=course_seat_types,
                    email_domains=request.data.get('email_domains'),
                    end_datetime=dateutil.parser.parse(request.data.get('end_datetime')),
                    max_uses=max_uses,
                    note=request.data.get('note'),
                    partner=partner,
                    price=request.data.get('price'),
                    quantity=request.data.get('quantity'),
                    start_datetime=dateutil.parser.parse(request.data.get('start_datetime')),
                    title=request.data.get('title'),
                    voucher_type=voucher_type
                )

                basket = prepare_basket(request, coupon_product)

                # Create an order now since payment is handled out of band via an invoice.
                client, __ = BusinessClient.objects.get_or_create(name=request.data.get('client'))
                invoice_data = self.create_update_data_dict(data=request.data, fields=Invoice.UPDATEABLE_INVOICE_FIELDS)
                response_data = self.create_order_for_invoice(
                    basket, coupon_id=coupon_product.id, client=client, invoice_data=invoice_data
                )

                return Response(response_data, status=status.HTTP_200_OK)
        except ValidationError as e:
            raise serializers.ValidationError(e.message)

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
            basket=basket,
            billing_address=None,
            order_number=order_metadata['number'],
            order_total=order_metadata['total'],
            request=self.request,
            shipping_address=None,
            shipping_charge=order_metadata['shipping_charge'],
            shipping_method=order_metadata['shipping_method'],
            user=basket.owner
        )

        # Invoice payment processor invocation.
        payment_processor = InvoicePayment
        payment_processor(self.request.site).handle_processor_response(
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
        """Update coupon depending on request data sent."""
        super(CouponViewSet, self).update(request, *args, **kwargs)

        coupon = self.get_object()
        vouchers = coupon.attr.coupon_vouchers.vouchers
        baskets = Basket.objects.filter(lines__product_id=coupon.id, status=Basket.SUBMITTED)
        data = self.create_update_data_dict(data=request.data, fields=CouponVouchers.UPDATEABLE_VOUCHER_FIELDS)

        if data:
            vouchers.all().update(**data)

        range_data = self.create_update_data_dict(data=request.data, fields=Range.UPDATABLE_RANGE_FIELDS)

        if range_data:
            voucher_range = vouchers.first().offers.first().benefit.range
            # Remove catalog if switching from single course to dynamic query
            if voucher_range.catalog:
                range_data['catalog'] = None
            Range.objects.filter(id=voucher_range.id).update(**range_data)

        benefit_value = request.data.get('benefit_value')
        if benefit_value:
            self.update_coupon_benefit_value(benefit_value=benefit_value, vouchers=vouchers, coupon=coupon)

        category_data = request.data.get('category')
        if category_data:
            category = Category.objects.get(name=category_data['name'])
            ProductCategory.objects.filter(product=coupon).update(category=category)

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

        offer_data = self.create_update_data_dict(data=request.data, fields=ConditionalOffer.UPDATABLE_OFFER_FIELDS)
        if offer_data:
            ConditionalOffer.objects.filter(vouchers__in=vouchers.all()).update(**offer_data)

        self.update_invoice_data(coupon, request.data)

        serializer = self.get_serializer(coupon)
        return Response(serializer.data)

    def create_update_data_dict(self, data, fields):
        """
        Creates a dictionary for updating model attributes.

        Arguments:
            data (QueryDict): Request data
            fields (list): List of updatable model fields

        Returns:
            update_dict (dict): Dictionary that will be used to update model objects.
        """
        update_dict = {}

        for field in fields:
            if field in data:
                if field == 'course_seat_types':
                    value = prepare_course_seat_types(data.get(field))
                    update_dict[field] = value
                elif field == 'max_uses':
                    value = data.get(field)
                    update_dict['max_global_applications'] = value
                else:
                    value = data.get(field)
                    update_dict[field.replace('invoice_', '')] = value
        return update_dict

    def update_coupon_benefit_value(self, benefit_value, coupon, vouchers):
        """
        Remove all offers from the vouchers and add a new offer
        Arguments:
            benefit_value (Decimal): Benefit value associated with a new offer
            coupon (Product): Coupon product associated with vouchers
            vouchers (ManyRelatedManager): Vouchers associated with the coupon to be updated
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
        invoice_data = self.create_update_data_dict(data=data, fields=Invoice.UPDATEABLE_INVOICE_FIELDS)

        if invoice_data:
            Invoice.objects.filter(order__lines__product=coupon).update(**invoice_data)

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

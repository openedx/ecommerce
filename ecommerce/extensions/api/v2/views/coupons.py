from __future__ import unicode_literals

import logging

import dateutil.parser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.models import BusinessClient
from ecommerce.coupons.utils import prepare_course_seat_types
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.serializers import CategorySerializer, CouponSerializer, CouponListSerializer
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import create_coupon_product, get_or_create_catalog
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import update_voucher_offer
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
                value = prepare_course_seat_types(data.get(field)) if field == 'course_seat_types' else data.get(field)
                update_dict[field.replace('invoice_', '')] = value
        return update_dict

    def get_category(self, category_data):
        try:
            return Category.objects.get(id=category_data['id'])
        except Category.DoesNotExist:
            raise ValueError(_('Category with ID {category_id} not found.'.format(category_id=category_data['id'])))

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
            try:
                self.validate_coupon_data(request.data)
            except ValidationError as exc:
                return Response(exc.message, status=status.HTTP_400_BAD_REQUEST)

            try:
                invoice_data = self.prepare_data(request)
            except ValueError as exc:
                return Response(exc.message, status=status.HTTP_400_BAD_REQUEST)

            response_data = self.create_coupon(invoice_data=invoice_data, request=request)
            return Response(response_data, status=status.HTTP_200_OK)

    def create_coupon(self, invoice_data, request):
        """
        Creates a coupon product, adds it to a basket and creates an order.
        Arguments:
            invoice_data (dict): Dictionary containing Invoice data
            request (HttpRequest): Request containing coupon data and partner information
        Returns:
            response_data (dict): Serialized coupon data.
        """
        coupon_data = request.data
        coupon_product = create_coupon_product(
            benefit_type=coupon_data.get('benefit_type'),
            benefit_value=coupon_data.get('benefit_value'),
            catalog=coupon_data.get('catalog'),
            catalog_query=coupon_data.get('catalog_query'),
            category=coupon_data.get('category'),
            code=coupon_data.get('code'),
            course_seat_types=coupon_data.get('course_seat_types'),
            end_datetime=coupon_data.get('end_datetime'),
            max_uses=coupon_data.get('max_uses'),
            note=coupon_data.get('note'),
            partner=request.site.siteconfiguration.partner,
            price=coupon_data.get('price'),
            quantity=coupon_data.get('quantity'),
            start_datetime=coupon_data.get('start_datetime'),
            title=coupon_data.get('title'),
            voucher_type=coupon_data.get('voucher_type')
        )

        basket = prepare_basket(request, coupon_product)

        # Create an order now since payment is handled out of band via an invoice.
        response_data = self.create_order_for_invoice(
            basket=basket,
            client=coupon_data.get('client'),
            coupon_id=coupon_product.id,
            invoice_data=invoice_data
        )

        return response_data

    def prepare_data(self, request):
        """
        Prepare request data for coupon creation.
        Arguments:
            request (HttpRequest): Request containing coupon data and partner information
        Returns:
            invoice_data (dict): Dictionary containing Invoice data.
        """
        data = request.data

        category_data = data.get('category')
        course_seat_types = data.get('course_seat_types')
        max_uses = data.get('max_uses')
        quantity = data.get('quantity')
        stock_record_ids = data.get('stock_record_ids')

        if category_data:
            data['category'] = self.get_category(category_data)

        data['client'], __ = BusinessClient.objects.get_or_create(name=data.get('client'))

        if course_seat_types:
            data['course_seat_types'] = prepare_course_seat_types(course_seat_types)

        data['end_datetime'] = dateutil.parser.parse(data.get('end_datetime'))

        # Maximum number of uses can be set for each voucher type and disturb
        # the predefined behaviours of the different voucher types. Therefor
        # here we enforce that the max_uses variable can't be used for SINGLE_USE
        # voucher types.
        data['max_uses'] = int(max_uses) if max_uses and data.get('voucher_type') != Voucher.SINGLE_USE else None

        if quantity:
            data['quantity'] = int(quantity)

        data['start_datetime'] = dateutil.parser.parse(data.get('start_datetime'))

        # When a black-listed course mode is received raise an exception.
        # Audit modes do not have a certificate type and therefore will raise
        # an AttributeError exception.
        if stock_record_ids:
            seats = Product.objects.filter(stockrecords__id__in=stock_record_ids)
            for seat in seats:
                try:
                    if seat.attr.certificate_type in settings.BLACK_LIST_COUPON_COURSE_MODES:
                        raise ValueError(_('Course mode not supported'))
                except AttributeError:
                    raise ValueError(_('Course mode not supported'))

            stock_records_string = ' '.join(str(id) for id in stock_record_ids)
            data['catalog'], __ = get_or_create_catalog(
                name='Catalog for stock records: {}'.format(stock_records_string),
                partner=request.site.siteconfiguration.partner,
                stock_record_ids=stock_record_ids
            )
        else:
            data['catalog'] = None

        return self.create_update_data_dict(data=request.data, fields=Invoice.UPDATEABLE_INVOICE_FIELDS)

    def validate_coupon_data(self, data):
        """
        Validates coupon data sent via request.
        Raises:
            ValidationError: If request data fields contains invalid values
        """
        # TODO: (SOL-1903) Move validation code to the Coupon serializer
        code = data.get('code')
        if code:
            try:
                Voucher.objects.get(code=code)
                raise ValidationError(_('A coupon with code {code} already exists.'.format(code=code)))
            except Voucher.DoesNotExist:
                pass

    def update(self, request, *args, **kwargs):
        """Update start and end dates of all vouchers associated with the coupon."""
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
            Range.objects.filter(id=voucher_range.id).update(**range_data)

        benefit_value = request.data.get('benefit_value')
        if benefit_value:
            self.update_coupon_benefit_value(benefit_value=benefit_value, vouchers=vouchers, coupon=coupon)

        category_data = request.data.get('category')
        if category_data:
            category = self.get_category(category_data)
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

        self.update_invoice_data(coupon, request.data)

        serializer = self.get_serializer(coupon)
        return Response(serializer.data)

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

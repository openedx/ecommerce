from __future__ import unicode_literals

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from oscar.core.loading import get_model
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.core.models import BusinessClient
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.coupons.utils import prepare_course_seat_types
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.serializers import CategorySerializer, CouponListSerializer, CouponSerializer
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import create_coupon_product, get_or_create_catalog
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import update_voucher_offer
from ecommerce.invoice.models import Invoice
from ecommerce.programs.constants import BENEFIT_PROXY_CLASS_MAP

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


class CouponViewSet(EdxOrderPlacementMixin, viewsets.ModelViewSet):
    """ Coupon resource. """
    permission_classes = (IsAuthenticated, IsAdminUser)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = ProductFilter

    def get_queryset(self):
        return Product.objects.filter(
            product_class__name=COUPON_PRODUCT_CLASS_NAME,
            stockrecords__partner=self.request.site.siteconfiguration.partner
        )

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
        try:
            with transaction.atomic():
                try:
                    cleaned_voucher_data = self.clean_voucher_request_data(request)
                except ValidationError as error:
                    logger.exception('Failed to create coupon. %s', error.message)
                    # FIXME This should ALWAYS return 400.
                    return Response(error.message, status=error.code or 400)

                try:
                    coupon_product = create_coupon_product(
                        benefit_type=cleaned_voucher_data['benefit_type'],
                        benefit_value=cleaned_voucher_data['benefit_value'],
                        catalog=cleaned_voucher_data['coupon_catalog'],
                        catalog_query=cleaned_voucher_data['catalog_query'],
                        category=cleaned_voucher_data['category'],
                        code=cleaned_voucher_data['code'],
                        course_catalog=cleaned_voucher_data['course_catalog'],
                        course_seat_types=cleaned_voucher_data['course_seat_types'],
                        email_domains=cleaned_voucher_data['email_domains'],
                        end_datetime=cleaned_voucher_data['end_datetime'],
                        enterprise_customer=cleaned_voucher_data['enterprise_customer'],
                        max_uses=cleaned_voucher_data['max_uses'],
                        note=cleaned_voucher_data['note'],
                        partner=cleaned_voucher_data['partner'],
                        price=cleaned_voucher_data['price'],
                        quantity=cleaned_voucher_data['quantity'],
                        start_datetime=cleaned_voucher_data['start_datetime'],
                        title=cleaned_voucher_data['title'],
                        voucher_type=cleaned_voucher_data['voucher_type'],
                        program_uuid=cleaned_voucher_data['program_uuid'],
                    )
                except (KeyError, IntegrityError) as error:
                    logger.exception('Coupon creation failed!')
                    return Response(str(error), status=status.HTTP_400_BAD_REQUEST)

                basket = prepare_basket(request, [coupon_product])

                # Create an order now since payment is handled out of band via an invoice.
                client, __ = BusinessClient.objects.get_or_create(name=request.data.get('client'))
                invoice_data = self.create_update_data_dict(data=request.data, fields=Invoice.UPDATEABLE_INVOICE_FIELDS)
                response_data = self.create_order_for_invoice(
                    basket, coupon_id=coupon_product.id, client=client, invoice_data=invoice_data
                )

                return Response(response_data, status=status.HTTP_200_OK)
        except ValidationError as e:
            raise serializers.ValidationError(e.message)

    @classmethod
    def clean_voucher_request_data(cls, request):
        """
        Helper method to return cleaned request data for voucher creation or
        raise validation error with error code.

        Arguments:
            request (HttpRequest): request with voucher data

        """
        benefit_type = request.data.get('benefit_type')
        category_data = request.data.get('category')
        code = request.data.get('code')
        course_catalog_data = request.data.get('course_catalog')
        enterprise_customer_data = request.data.get('enterprise_customer')
        course_seat_types = request.data.get('course_seat_types')
        max_uses = request.data.get('max_uses')
        partner = request.site.siteconfiguration.partner
        stock_record_ids = request.data.get('stock_record_ids')
        voucher_type = request.data.get('voucher_type')
        program_uuid = request.data.get('program_uuid')

        if benefit_type not in (Benefit.PERCENTAGE, Benefit.FIXED,):
            raise ValidationError('Benefit type [{type}] is not allowed'.format(type=benefit_type))

        if code and Voucher.does_exist(code):
            validation_message = 'A coupon with code {code} already exists.'.format(code=code)
            raise ValidationError(validation_message)

        if course_seat_types:
            try:
                course_seat_types = prepare_course_seat_types(course_seat_types)
            except (AttributeError, TypeError) as exception:
                validation_message = 'Invalid course seat types data: {}'.format(exception.message)
                raise ValidationError(validation_message)

        try:
            category = Category.objects.get(name=category_data['name'])
        except Category.DoesNotExist:
            validation_message = 'Category "{category_name}" not found.'.format(category_name=category_data['name'])
            # FIXME 404 is the wrong response code to use here.
            raise ValidationError(validation_message, code=status.HTTP_404_NOT_FOUND)
        except (KeyError, TypeError):
            validation_message = 'Invalid Coupon Category data.'
            raise ValidationError(validation_message)

        try:
            course_catalog = course_catalog_data['id'] if course_catalog_data else None
        except (KeyError, TypeError):
            validation_message = 'Unexpected catalog data format received for coupon.'
            raise ValidationError(validation_message)

        try:
            enterprise_customer = enterprise_customer_data['id'] if enterprise_customer_data else None
        except (KeyError, TypeError):
            validation_message = 'Unexpected EnterpriseCustomer data format received for coupon.'
            raise ValidationError(validation_message)

        coupon_catalog = cls.get_coupon_catalog(stock_record_ids, partner)

        return {
            'benefit_type': benefit_type,
            'benefit_value': request.data.get('benefit_value'),
            'coupon_catalog': coupon_catalog,
            'catalog_query': request.data.get('catalog_query'),
            'category': category,
            'code': code,
            'course_catalog': course_catalog,
            'course_seat_types': course_seat_types,
            'email_domains': request.data.get('email_domains'),
            'end_datetime': request.data.get('end_datetime'),
            'enterprise_customer': enterprise_customer,
            'max_uses': max_uses,
            'note': request.data.get('note'),
            'partner': partner,
            'price': request.data.get('price'),
            'quantity': request.data.get('quantity'),
            'start_datetime': request.data.get('start_datetime'),
            'title': request.data.get('title'),
            'voucher_type': voucher_type,
            'program_uuid': program_uuid,
        }

    @classmethod
    def get_coupon_catalog(cls, stock_record_ids, partner):
        """
        Validate stock_record_ids and return a coupon catalog if applicable.

        When a black-listed course mode is received raise an exception.
        Audit modes do not have a certificate type and therefore will raise
        an AttributeError exception.
        """
        if not stock_record_ids:
            return None

        seats = Product.objects.filter(stockrecords__id__in=stock_record_ids)
        for seat in seats:
            try:
                if seat.attr.certificate_type in settings.BLACK_LIST_COUPON_COURSE_MODES:
                    validation_message = 'Course mode not supported'
                    raise ValidationError(validation_message)
            except AttributeError:
                validation_message = 'Course mode not supported'
                raise ValidationError(validation_message)

        stock_records_string = ' '.join(str(id) for id in stock_record_ids)
        coupon_catalog, __ = get_or_create_catalog(
            name='Catalog for stock records: {}'.format(stock_records_string),
            partner=partner,
            stock_record_ids=stock_record_ids
        )
        return coupon_catalog

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

    def update_range_data(self, request, vouchers):
        """
        Update the range data for a particular request.
        """
        range_data = self.create_update_data_dict(data=request.data, fields=Range.UPDATABLE_RANGE_FIELDS)

        if not range_data:
            return None

        voucher_range = vouchers.first().offers.first().benefit.range
        enterprise_customer_data = request.data.get('enterprise_customer')

        # Remove catalog if switching from single course to dynamic query
        # In case of enterprise, range_data has enterprise data in it as enterprise is defined in UPDATABLE_RANGE_FIELDS
        # so Catalog should not be None if there is an enterprise is associated with it.
        if voucher_range.catalog:
            if not enterprise_customer_data:
                range_data['catalog'] = None

            if enterprise_customer_data and range_data.get('catalog_query'):
                range_data['catalog'] = None

        course_catalog_data = request.data.get('course_catalog')
        if course_catalog_data:
            course_catalog = course_catalog_data.get('id')
            range_data['course_catalog'] = course_catalog

            # Remove catalog_query, switching from the dynamic query coupon to
            # course catalog coupon
            range_data['catalog_query'] = None
        else:
            range_data['course_catalog'] = None

        if enterprise_customer_data:
            range_data['enterprise_customer'] = enterprise_customer_data.get('id')
        else:
            range_data['enterprise_customer'] = None

        for attr, value in range_data.iteritems():
            setattr(voucher_range, attr, value)

        voucher_range.save()

    def update(self, request, *args, **kwargs):
        """Update coupon depending on request data sent."""
        try:
            super(CouponViewSet, self).update(request, *args, **kwargs)

            coupon = self.get_object()
            vouchers = coupon.attr.coupon_vouchers.vouchers
            baskets = Basket.objects.filter(lines__product_id=coupon.id, status=Basket.SUBMITTED)
            data = self.create_update_data_dict(data=request.data, fields=CouponVouchers.UPDATEABLE_VOUCHER_FIELDS)

            if data:
                vouchers.all().update(**data)

            self.update_range_data(request, vouchers)

            program_uuid = request.data.get('program_uuid')
            benefit_value = request.data.get('benefit_value')
            if benefit_value or program_uuid:
                self.update_coupon_offer(benefit_value=benefit_value, vouchers=vouchers,
                                         coupon=coupon, program_uuid=program_uuid)

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

            self.update_offer_data(request.data, vouchers, coupon.id)
            self.update_invoice_data(coupon, request.data)

            serializer = self.get_serializer(coupon)
            return Response(serializer.data)
        except ValidationError as error:
            error_message = 'Failed to update Coupon [{coupon_id}]. {msg}'.format(
                coupon_id=coupon.id,
                msg=error.message
            )
            logger.exception(error_message)
            raise serializers.ValidationError(error_message)

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

    def update_coupon_offer(self, coupon, vouchers, benefit_value=None, program_uuid=None):
        """
        Remove all offers from the vouchers and add a new offer
        Arguments:
            coupon (Product): Coupon product associated with vouchers
            vouchers (ManyRelatedManager): Vouchers associated with the coupon to be updated
            benefit_value (Decimal): Benefit value associated with a new offer
            program_uuid (str): Program UUID
        """
        voucher_offers = vouchers.first().offers
        voucher_offer = voucher_offers.first()

        if program_uuid:
            Condition.objects.filter(
                program_uuid=voucher_offer.condition.program_uuid
            ).update(program_uuid=program_uuid)

        # The program uuid (if program coupon) is required for the benefit and condition update logic
        program_uuid = program_uuid or voucher_offer.condition.program_uuid

        new_offer = update_voucher_offer(
            offer=voucher_offer,
            benefit_value=benefit_value or voucher_offer.benefit.value,
            benefit_type=voucher_offer.benefit.type or BENEFIT_PROXY_CLASS_MAP[voucher_offer.benefit.proxy_class],
            coupon=coupon,
            max_uses=voucher_offer.max_global_applications,
            program_uuid=program_uuid
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

    def update_offer_data(self, data, vouchers, coupon_id):
        offer_data = self.create_update_data_dict(data=data, fields=ConditionalOffer.UPDATABLE_OFFER_FIELDS)

        if offer_data:
            if offer_data.get('max_global_applications') is not None:
                if vouchers.first().usage == Voucher.SINGLE_USE:
                    log_message_and_raise_validation_error(
                        'Failed to update Coupon [{coupon_id}]. '
                        'max_global_applications field cannot be set for voucher type [{voucher_type}].'.format(
                            coupon_id=coupon_id,
                            voucher_type=Voucher.SINGLE_USE
                        )
                    )
                try:
                    offer_data['max_global_applications'] = int(offer_data['max_global_applications'])
                    if offer_data['max_global_applications'] < 1:
                        raise ValueError
                except ValueError:
                    raise ValidationError('max_global_applications field must be a positive number.')
            ConditionalOffer.objects.filter(vouchers__in=vouchers.all()).update(**offer_data)

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

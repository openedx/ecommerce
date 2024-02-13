

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from oscar.core.loading import get_model
from rest_framework import generics, serializers, status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.core.models import BusinessClient
from ecommerce.coupons.utils import prepare_course_seat_types
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.serializers import (
    CategorySerializer,
    CouponListSerializer,
    CouponSerializer,
    CouponUpdateSerializer
)
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import (
    attach_or_update_contract_metadata_on_coupon,
    create_coupon_product,
    get_or_create_catalog
)
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import (
    get_or_create_enterprise_offer,
    update_voucher_offer,
    update_voucher_with_enterprise_offer
)
from ecommerce.invoice.models import Invoice

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

DEPRECATED_COUPON_CATEGORIES = ['Bulk Enrollment']


class CouponViewSet(EdxOrderPlacementMixin, viewsets.ModelViewSet):
    """ Coupon resource. """
    permission_classes = (IsAuthenticated, IsAdminUser)
    filterset_class = ProductFilter

    def get_queryset(self):
        product_filter = Product.objects.filter(
            product_class__name=COUPON_PRODUCT_CLASS_NAME,
            stockrecords__partner=self.request.site.siteconfiguration.partner
        )
        # Now that we have switched completely to using enterprise offers, ensure that enterprise coupons do not show up
        # in the regular coupon list view.
        return product_filter.exclude(
            attributes__code='enterprise_customer_uuid',
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CouponListSerializer
        if self.action == 'update':
            return CouponUpdateSerializer
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
                    serializer = self.get_serializer(data=request.data)
                    serializer.is_valid(raise_exception=True)
                    self.validate_access_for_enterprise(request.data)
                    cleaned_voucher_data = self.clean_voucher_request_data(
                        request.data, request.site.siteconfiguration.partner
                    )
                except ValidationError as error:
                    logger.exception('Failed to create coupon. %s', error.message)
                    # FIXME This should ALWAYS return 400.
                    return Response(error.message, status=error.code or 400)

                try:
                    coupon_product = self.create_coupon_and_vouchers(cleaned_voucher_data)
                except (KeyError, IntegrityError) as error:
                    logger.exception('Coupon creation failed!')
                    return Response(str(error), status=status.HTTP_400_BAD_REQUEST)

                basket = prepare_basket(request, [coupon_product])

                # Create an order now since payment is handled out of band via an invoice.
                client, __ = BusinessClient.objects.update_or_create(
                    name=cleaned_voucher_data['enterprise_customer_name'] or request.data.get('client'),
                )
                invoice_data = self.create_update_data_dict(data=request.data, fields=Invoice.UPDATEABLE_INVOICE_FIELDS)
                response_data = self.create_order_for_invoice(
                    basket, coupon_id=coupon_product.id, client=client, invoice_data=invoice_data
                )
                if cleaned_voucher_data['notify_email']:
                    self.send_codes_availability_email(
                        self.request.site,
                        cleaned_voucher_data['notify_email'],
                        cleaned_voucher_data['enterprise_customer'],
                        coupon_product.id
                    )
                return Response(response_data, status=status.HTTP_200_OK)
        except ValidationError as e:
            raise serializers.ValidationError(e.message)

    @staticmethod
    def send_codes_availability_email(site, email_address, enterprise_id, coupon_id):
        pass

    def create_coupon_and_vouchers(self, cleaned_voucher_data):
        return create_coupon_product(
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
            enterprise_customer_catalog=cleaned_voucher_data['enterprise_customer_catalog'],
            max_uses=cleaned_voucher_data['max_uses'],
            note=cleaned_voucher_data['note'],
            partner=cleaned_voucher_data['partner'],
            price=cleaned_voucher_data['price'],
            quantity=cleaned_voucher_data['quantity'],
            start_datetime=cleaned_voucher_data['start_datetime'],
            title=cleaned_voucher_data['title'],
            voucher_type=cleaned_voucher_data['voucher_type'],
            program_uuid=cleaned_voucher_data['program_uuid'],
            site=self.request.site,
            sales_force_id=cleaned_voucher_data['sales_force_id'],
            salesforce_opportunity_line_item=cleaned_voucher_data['salesforce_opportunity_line_item'],
        )

    def validate_access_for_enterprise(self, request_data):
        enterprise_customer_data = request_data.get('enterprise_customer')
        if enterprise_customer_data and enterprise_customer_data.get('id'):
            raise ValidationError('Enterprise coupons can no longer be created or updated from this endpoint.')

    @classmethod
    def clean_voucher_request_data(cls, request_data, partner):
        """
        Helper method to return cleaned request data for voucher creation or
        raise validation error with error code.

        Arguments:
            request (dict): request's data with voucher data
            partner (str): the request's site's partner

        """
        benefit_type = request_data.get('benefit_type')
        category_data = request_data.get('category')
        code = request_data.get('code')
        course_catalog_data = request_data.get('course_catalog')
        enterprise_customer_data = request_data.get('enterprise_customer')
        course_seat_types = request_data.get('course_seat_types')
        max_uses = request_data.get('max_uses')
        stock_record_ids = request_data.get('stock_record_ids')
        voucher_type = request_data.get('voucher_type')
        program_uuid = request_data.get('program_uuid')
        notify_email = request_data.get('notify_email')

        if benefit_type not in (Benefit.PERCENTAGE, Benefit.FIXED,):
            raise ValidationError('Benefit type [{type}] is not allowed'.format(type=benefit_type))

        if code and Voucher.does_exist(code):
            validation_message = 'A coupon with code {code} already exists.'.format(code=code)
            raise ValidationError(validation_message)

        if course_seat_types:
            try:
                course_seat_types = prepare_course_seat_types(course_seat_types)
            except (AttributeError, TypeError) as exception:
                validation_message = 'Invalid course seat types data: {}'.format(str(exception))
                raise ValidationError(validation_message) from exception

        try:
            category = Category.objects.get(name=category_data['name'])
        except Category.DoesNotExist as category_no_exist:
            validation_message = 'Category "{category_name}" not found.'.format(category_name=category_data['name'])
            # FIXME 404 is the wrong response code to use here.
            raise ValidationError(validation_message, code=status.HTTP_404_NOT_FOUND) from category_no_exist
        except (KeyError, TypeError) as key_type_errors:
            validation_message = 'Invalid Coupon Category data.'
            raise ValidationError(validation_message) from key_type_errors

        try:
            course_catalog = course_catalog_data['id'] if course_catalog_data else None
        except (KeyError, TypeError) as key_type_errors:
            validation_message = 'Unexpected catalog data format received for coupon.'
            raise ValidationError(validation_message) from key_type_errors

        try:
            enterprise_customer = enterprise_customer_data['id'] if enterprise_customer_data else None
            enterprise_customer_name = enterprise_customer_data.get('name') if enterprise_customer_data else None
        except (KeyError, TypeError) as key_type_errors:
            validation_message = 'Unexpected EnterpriseCustomer data format received for coupon.'
            raise ValidationError(validation_message) from key_type_errors

        if notify_email:
            try:
                validate_email(notify_email)
            except ValidationError as validation_error:
                raise ValidationError('Notification email must be a valid email address.') from validation_error

        coupon_catalog = cls.get_coupon_catalog(stock_record_ids, partner)

        return {
            'benefit_type': benefit_type,
            'benefit_value': request_data.get('benefit_value'),
            'coupon_catalog': coupon_catalog,
            'catalog_query': request_data.get('catalog_query'),
            'category': category,
            'code': code,
            'course_catalog': course_catalog,
            'course_seat_types': course_seat_types,
            'email_domains': request_data.get('email_domains'),
            'end_datetime': request_data.get('end_datetime'),
            'enterprise_customer': enterprise_customer,
            'enterprise_customer_name': enterprise_customer_name,
            'enterprise_customer_catalog': request_data.get('enterprise_customer_catalog'),
            'max_uses': max_uses,
            'note': request_data.get('note'),
            'partner': partner,
            'price': request_data.get('price'),
            'quantity': request_data.get('quantity'),
            'start_datetime': request_data.get('start_datetime'),
            'title': request_data.get('title'),
            'voucher_type': voucher_type,
            'program_uuid': program_uuid,
            'notify_email': notify_email,
            'contract_discount_type': request_data.get('contract_discount_type'),
            'contract_discount_value': request_data.get('contract_discount_value'),
            'prepaid_invoice_amount': request_data.get('prepaid_invoice_amount'),
            'sales_force_id': request_data.get('sales_force_id'),
            'salesforce_opportunity_line_item': request_data.get('salesforce_opportunity_line_item'),
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
            except AttributeError as attribute_error:
                validation_message = 'Course mode not supported'
                raise ValidationError(validation_message) from attribute_error

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

    def update(self, request, *args, **kwargs):
        """Update coupon depending on request data sent."""
        try:
            super(CouponViewSet, self).update(request, *args, **kwargs)
            coupon = self.get_object()
            vouchers = coupon.attr.coupon_vouchers.vouchers.all()
            self.update_voucher_data(request.data, vouchers)
            self.update_range_data(request.data, vouchers)
            self.update_offer_data(request.data, vouchers, self.request.site)
            self.update_coupon_product_data(request.data, coupon)
            self.update_invoice_data(request.data, coupon)
            serializer = self.get_serializer(coupon)
            return Response(serializer.data)
        except ValidationError as error:
            error_message = 'Failed to update Coupon [{coupon_id}]. {msg}'.format(
                coupon_id=kwargs.get('pk'),
                msg=error.message
            )
            logger.exception(error_message)
            raise serializers.ValidationError(error_message)

    def update_voucher_data(self, request_data, vouchers):
        data = self.create_update_data_dict(data=request_data, fields=CouponVouchers.UPDATEABLE_VOUCHER_FIELDS)
        if data:
            vouchers.update(**data)

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
                else:
                    value = data.get(field)
                    update_dict[field.replace('invoice_', '')] = value
        return update_dict

    def update_range_data(self, request_data, vouchers):
        """
        Update the range data for a particular request.
        """
        range_data = self.create_update_data_dict(data=request_data, fields=Range.UPDATABLE_RANGE_FIELDS)

        if not range_data:
            return

        voucher_range = vouchers.first().original_offer.benefit.range

        enterprise_customer_data = request_data.get('enterprise_customer')

        # Remove catalog if switching from single course to dynamic query
        # In case of enterprise, range_data has enterprise data in it as enterprise is defined in UPDATABLE_RANGE_FIELDS
        # so Catalog should not be None if there is an enterprise is associated with it.
        if voucher_range.catalog:
            if not enterprise_customer_data:
                range_data['catalog'] = None

            if enterprise_customer_data and range_data.get('catalog_query'):
                range_data['catalog'] = None

        course_catalog_data = request_data.get('course_catalog')
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

        if 'enterprise_customer_catalog' in request_data:
            range_data['enterprise_customer_catalog'] = request_data.get('enterprise_customer_catalog') or None

        for attr, value in range_data.items():
            setattr(voucher_range, attr, value)

        voucher_range.save()

    def update_coupon_product_data(self, request_data, coupon):
        baskets = Basket.objects.filter(lines__product_id=coupon.id, status=Basket.SUBMITTED)

        category_data = request_data.get('category')
        if category_data:
            category = Category.objects.get(name=category_data['name'])
            ProductCategory.objects.filter(product=coupon).update(category=category)

        client_username = request_data.get('client')
        enterprise_customer_data = request_data.get('enterprise_customer')
        enterprise_customer = enterprise_customer_data.get('id', None) if enterprise_customer_data else None
        enterprise_customer_name = enterprise_customer_data.get('name', None) if enterprise_customer_data else None
        if client_username or enterprise_customer:
            client, __ = BusinessClient.objects.update_or_create(
                name=enterprise_customer_name or client_username,
            )
            Invoice.objects.filter(order__basket=baskets.first()).update(business_client=client)
            coupon.attr.enterprise_customer_uuid = enterprise_customer

        coupon_price = request_data.get('price')
        if coupon_price:
            StockRecord.objects.filter(product=coupon).update(price_excl_tax=coupon_price)

        note = request_data.get('note')
        if note is not None:
            coupon.attr.note = note

        if 'notify_email' in request_data:
            coupon.attr.notify_email = request_data.get('notify_email')

        sales_force_id = request_data.get('sales_force_id')
        if sales_force_id is not None:
            coupon.attr.sales_force_id = sales_force_id

        salesforce_opportunity_line_item = request_data.get('salesforce_opportunity_line_item')
        if salesforce_opportunity_line_item is not None:
            coupon.attr.salesforce_opportunity_line_item = salesforce_opportunity_line_item

        if 'inactive' in request_data:
            coupon.attr.inactive = request_data.get('inactive')

        coupon.save()

        discount_value = request_data.get('contract_discount_value')
        prepaid_invoice_amount = request_data.get('prepaid_invoice_amount')
        if discount_value is not None or prepaid_invoice_amount is not None:
            discount_type = request_data.get('contract_discount_type')
            logger.info(
                "Calling attach_or_update_contract_metadata_on_coupon "
                "from api/v2/views/coupons.py for coupon [%s]",
                coupon.id
            )
            attach_or_update_contract_metadata_on_coupon(
                coupon,
                discount_type=discount_type,
                discount_value=discount_value,
                amount_paid=prepaid_invoice_amount,
            )

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
        program_uuid = request_data.get('program_uuid')
        benefit_value = request_data.get('benefit_value')
        enterprise_customer_data = request_data.get('enterprise_customer')
        enterprise_customer = enterprise_customer_data.get('id', None) if enterprise_customer_data else None
        enterprise_catalog = request_data.get('enterprise_customer_catalog') or None
        max_uses = request_data.get('max_uses')
        email_domains = request_data.get('email_domains')

        for voucher in vouchers:
            updated_original_offer = update_voucher_offer(
                offer=voucher.original_offer,
                benefit_value=benefit_value,
                max_uses=max_uses,
                program_uuid=program_uuid,
                email_domains=email_domains,
                site=site,
            )
            updated_enterprise_offer = None
            if voucher.enterprise_offer:
                updated_enterprise_offer = update_voucher_with_enterprise_offer(
                    offer=voucher.enterprise_offer,
                    benefit_value=benefit_value,
                    max_uses=max_uses,
                    enterprise_customer=enterprise_customer,
                    enterprise_catalog=enterprise_catalog,
                    email_domains=email_domains,
                    site=site,
                )
            elif enterprise_customer:
                # If we are performing an update on an existing enterprise coupon,
                # we need to ensure the enterprise offer is created if it didn't already exist.
                updated_enterprise_offer = get_or_create_enterprise_offer(
                    benefit_value=benefit_value or voucher.original_offer.benefit.value,
                    benefit_type=voucher.original_offer.benefit.type,
                    enterprise_customer=enterprise_customer,
                    enterprise_customer_catalog=enterprise_catalog,
                    offer_name=voucher.original_offer.name + " ENT Offer",
                    max_uses=max_uses or voucher.original_offer.max_global_applications,
                    email_domains=email_domains or voucher.original_offer.email_domains,
                    site=site or voucher.original_offer.site,
                )
            voucher.offers.clear()
            voucher.offers.add(updated_original_offer)
            if updated_enterprise_offer:
                voucher.offers.add(updated_enterprise_offer)

    def update_invoice_data(self, request_data, coupon):
        """
        Update the invoice data.

        Arguments:
            request_data (dict): The request's data from which the invoice data is retrieved
                         and used for the updated.
            coupon (Product): The coupon product with which the invoice is retrieved.
        """
        invoice_data = self.create_update_data_dict(data=request_data, fields=Invoice.UPDATEABLE_INVOICE_FIELDS)

        if invoice_data:
            Invoice.objects.filter(order__lines__product=coupon).update(**invoice_data)

    def destroy(self, request, pk):  # pylint: disable=unused-argument, arguments-differ
        try:
            coupon = get_object_or_404(Product, pk=pk)
            self.perform_destroy(coupon)
        except Http404:
            return Response(status=404)
        return Response(status=204)

    def perform_destroy(self, coupon):  # pylint: disable=arguments-differ
        Voucher.objects.filter(coupon_vouchers__coupon=coupon).delete()
        StockRecord.objects.filter(product=coupon).delete()
        coupon.delete()


class CouponCategoriesListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        parent_category = Category.objects.get(slug='coupons')
        return parent_category.get_children().exclude(name__in=DEPRECATED_COUPON_CATEGORIES)

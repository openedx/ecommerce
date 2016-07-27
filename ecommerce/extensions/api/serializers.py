"""Serializers for data manipulated by ecommerce API endpoints."""
from __future__ import unicode_literals

from decimal import Decimal
import logging

from dateutil.parser import parse
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import get_user_model
from oscar.core.loading import get_model, get_class
from rest_framework import serializers
from rest_framework.reverse import reverse
import waffle

from ecommerce.core.constants import ISO_8601_FORMAT, COURSE_ID_REGEX
from ecommerce.core.models import Site, SiteConfiguration
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.courses.models import Course
from ecommerce.coupons.utils import get_seats_from_query
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
BillingAddress = get_model('order', 'BillingAddress')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Line = get_model('order', 'Line')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
Partner = get_model('partner', 'Partner')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')
Refund = get_model('refund', 'Refund')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
User = get_user_model()

COURSE_DETAIL_VIEW = 'api:v2:course-detail'
PRODUCT_DETAIL_VIEW = 'api:v2:product-detail'


class ProductPaymentInfoMixin(serializers.ModelSerializer):
    """ Mixin class used for retrieving price information from products. """
    price = serializers.SerializerMethodField()

    def get_price(self, product):
        info = self._get_info(product)
        if info.availability.is_available_to_buy:
            return serializers.DecimalField(max_digits=10, decimal_places=2).to_representation(info.price.excl_tax)
        return None

    def _get_info(self, product):
        return Selector().strategy(
            request=self.context.get('request')
        ).fetch_for_product(product)


class BillingAddressSerializer(serializers.ModelSerializer):
    """Serializes a Billing Address. """
    city = serializers.CharField(max_length=255, source='line4')

    class Meta(object):
        model = BillingAddress
        fields = ('first_name', 'last_name', 'line1', 'line2', 'postcode', 'state', 'country', 'city')


class UserSerializer(serializers.ModelSerializer):
    """Serializes user information. """
    class Meta(object):
        model = User
        fields = ('email', 'username')


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """ Serializer for ProductAttributeValue objects. """
    name = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    def get_name(self, instance):
        return instance.attribute.name

    def get_code(self, instance):
        return instance.attribute.code

    def get_value(self, obj):
        if obj.attribute.name == 'Coupon vouchers':
            request = self.context.get('request')
            vouchers = obj.value.vouchers.all()
            serializer = VoucherSerializer(vouchers, many=True, context={'request': request})
            return serializer.data
        return obj.value

    class Meta(object):
        model = ProductAttributeValue
        fields = ('name', 'code', 'value',)


class StockRecordSerializer(serializers.ModelSerializer):
    """ Serializer for stock record objects. """

    class Meta(object):
        model = StockRecord
        fields = ('id', 'product', 'partner', 'partner_sku', 'price_currency', 'price_excl_tax',)


class PartialStockRecordSerializerForUpdate(StockRecordSerializer):
    """ Stock record objects serializer for PUT requests.

    Allowed fields to update are 'price_currency' and 'price_excl_tax'.
    """

    class Meta(object):
        model = StockRecord
        fields = ('price_currency', 'price_excl_tax',)


class ProductSerializer(ProductPaymentInfoMixin, serializers.HyperlinkedModelSerializer):
    """ Serializer for Products. """
    attribute_values = serializers.SerializerMethodField()
    product_class = serializers.SerializerMethodField()
    is_available_to_buy = serializers.SerializerMethodField()
    stockrecords = StockRecordSerializer(many=True, read_only=True)

    def get_attribute_values(self, product):
        request = self.context.get('request')
        serializer = ProductAttributeValueSerializer(
            product.attr,
            many=True,
            read_only=True,
            context={'request': request}
        )
        return serializer.data

    def get_product_class(self, product):
        return product.get_product_class().name

    def get_is_available_to_buy(self, product):
        info = self._get_info(product)
        return info.availability.is_available_to_buy

    class Meta(object):
        model = Product
        fields = ('id', 'url', 'structure', 'product_class', 'title', 'price', 'expires', 'attribute_values',
                  'is_available_to_buy', 'stockrecords',)
        extra_kwargs = {
            'url': {'view_name': PRODUCT_DETAIL_VIEW},
        }


class LineSerializer(serializers.ModelSerializer):
    """Serializer for parsing line item data."""
    product = ProductSerializer()

    class Meta(object):
        model = Line
        fields = ('title', 'quantity', 'description', 'status', 'line_price_excl_tax', 'unit_price_excl_tax', 'product')


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for parsing order data."""
    date_placed = serializers.DateTimeField(format=ISO_8601_FORMAT)
    lines = LineSerializer(many=True)
    billing_address = BillingAddressSerializer(allow_null=True)
    user = UserSerializer()

    class Meta(object):
        model = Order
        fields = ('number', 'date_placed', 'status', 'currency', 'total_excl_tax', 'lines', 'billing_address', 'user')


class PaymentProcessorSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """ Serializer to use with instances of processors.BasePaymentProcessor """

    def to_representation(self, instance):
        """ Serialize instances as a string instead of a mapping object. """
        return instance.NAME


class RefundSerializer(serializers.ModelSerializer):
    """ Serializer for Refund objects. """

    class Meta(object):
        model = Refund


class CourseSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.RegexField(COURSE_ID_REGEX, max_length=255)
    products = ProductSerializer(many=True)
    products_url = serializers.SerializerMethodField()
    last_edited = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super(CourseSerializer, self).__init__(*args, **kwargs)

        # NOTE: All normal initializations of the serializer will include a context kwarg.
        # We use dict.get() here because Swagger does not include context when generating docs.
        include_products = kwargs.get('context', {}).pop('include_products', False)
        if not include_products:
            self.fields.pop('products', None)

    def get_last_edited(self, obj):
        return obj.history.latest().history_date.strftime(ISO_8601_FORMAT)

    def get_products_url(self, obj):
        return reverse('api:v2:course-product-list', kwargs={'parent_lookup_course_id': obj.id},
                       request=self.context['request'])

    class Meta(object):
        model = Course
        fields = ('id', 'url', 'name', 'verification_deadline', 'type', 'products_url', 'last_edited', 'products')
        read_only_fields = ('type', 'products')
        extra_kwargs = {
            'url': {'view_name': COURSE_DETAIL_VIEW}
        }


class AtomicPublicationSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for saving and publishing a Course and associated products.

    Using a ModelSerializer for the Course data makes it difficult to use this serializer to handle updates.
    The automatically applied validation logic rejects course IDs which already exist in the database.
    """
    id = serializers.RegexField(COURSE_ID_REGEX, max_length=255)
    name = serializers.CharField(max_length=255)
    # Verification deadline should only be required if the course actually requires verification.
    verification_deadline = serializers.DateTimeField(required=False, allow_null=True)
    products = serializers.ListField()

    def __init__(self, *args, **kwargs):
        super(AtomicPublicationSerializer, self).__init__(*args, **kwargs)

        self.access_token = kwargs['context'].pop('access_token')
        self.partner = kwargs['context'].pop('partner', None)

    def validate_products(self, products):
        """Validate product data."""
        for product in products:
            # Verify that each product is intended to be a Seat.
            product_class = product.get('product_class')
            if product_class != 'Seat':
                raise serializers.ValidationError(
                    _(u"Invalid product class [{product_class}] requested.".format(product_class=product_class))
                )

            # Verify that attributes required to create a Seat are present.
            attrs = self._flatten(product['attribute_values'])
            if attrs.get('id_verification_required') is None:
                raise serializers.ValidationError(_(u"Products must indicate whether ID verification is required."))

            # Verify that a price is present.
            if product.get('price') is None:
                raise serializers.ValidationError(_(u"Products must have a price."))

        return products

    def get_partner(self):
        """Validate partner"""
        if not self.partner:
            partner = Partner.objects.get(id=1)
            return partner

        return self.partner

    def save(self):
        """Save and publish Course and associated products."

        Returns:
            tuple: A Boolean indicating whether the Course was created, an Exception,
                if one was raised (else None), and a message for the user, if necessary (else None).
        """
        course_id = self.validated_data['id']
        course_name = self.validated_data['name']
        course_verification_deadline = self.validated_data.get('verification_deadline')
        products = self.validated_data['products']
        partner = self.get_partner()

        try:
            if not waffle.switch_is_active('publish_course_modes_to_lms'):
                message = _(
                    u'Course [{course_id}] was not published to LMS '
                    u'because the switch [publish_course_modes_to_lms] is disabled. '
                    u'To avoid ghost SKUs, data has not been saved.'
                ).format(course_id=course_id)

                raise Exception(message)

            # Explicitly delimit operations which will be rolled back if an exception is raised.
            with transaction.atomic():
                course, created = Course.objects.get_or_create(id=course_id)
                course.name = course_name
                course.verification_deadline = course_verification_deadline
                course.save()

                for product in products:
                    attrs = self._flatten(product['attribute_values'])

                    # Extract arguments required for Seat creation, deserializing as necessary.
                    certificate_type = attrs.get('certificate_type', '')
                    create_enrollment_code = product['course'].get('create_enrollment_code') and \
                        self.context['request'].site.siteconfiguration.enable_enrollment_codes
                    id_verification_required = attrs['id_verification_required']
                    price = Decimal(product['price'])

                    # Extract arguments which are optional for Seat creation, deserializing as necessary.
                    expires = product.get('expires')
                    expires = parse(expires) if expires else None
                    credit_provider = attrs.get('credit_provider')
                    credit_hours = attrs.get('credit_hours')
                    credit_hours = int(credit_hours) if credit_hours else None

                    course.create_or_update_seat(
                        certificate_type,
                        id_verification_required,
                        price,
                        partner,
                        expires=expires,
                        credit_provider=credit_provider,
                        credit_hours=credit_hours,
                        create_enrollment_code=create_enrollment_code
                    )

                resp_message = course.publish_to_lms(access_token=self.access_token)
                published = (resp_message is None)

                if published:
                    return created, None, None
                else:
                    raise Exception(resp_message)

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(u'Failed to save and publish [%s]: [%s]', course_id, e.message)
            return False, e, e.message

    def _flatten(self, attrs):
        """Transform a list of attribute names and values into a dictionary keyed on the names."""
        return {attr['name']: attr['value'] for attr in attrs}


class PartnerSerializer(serializers.ModelSerializer):
    """Serializer for the Partner object"""
    catalogs = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    def get_products(self, obj):
        return reverse(
            'api:v2:partner-product-list',
            kwargs={'parent_lookup_stockrecords__partner_id': obj.id},
            request=self.context['request']
        )

    def get_catalogs(self, obj):
        return reverse(
            'api:v2:partner-catalogs-list',
            kwargs={'parent_lookup_partner_id': obj.id},
            request=self.context['request']
        )

    class Meta(object):
        model = Partner
        fields = ('id', 'name', 'short_code', 'catalogs', 'products')


class CatalogSerializer(serializers.ModelSerializer):
    """ Serializer for Catalogs. """
    products = serializers.SerializerMethodField()

    class Meta(object):
        model = Catalog
        fields = ('id', 'partner', 'name', 'products')

    def get_products(self, obj):
        return reverse(
            'api:v2:catalog-product-list',
            kwargs={'parent_lookup_stockrecords__catalogs': obj.id},
            request=self.context['request']
        )


class BenefitSerializer(serializers.ModelSerializer):
    value = serializers.IntegerField()

    class Meta(object):
        model = Benefit
        fields = ('type', 'value')


class VoucherSerializer(serializers.ModelSerializer):
    is_available_to_user = serializers.SerializerMethodField()
    benefit = serializers.SerializerMethodField()
    redeem_url = serializers.SerializerMethodField()

    def get_is_available_to_user(self, obj):
        request = self.context.get('request')
        return obj.is_available_to_user(user=request.user)

    def get_benefit(self, obj):
        benefit = obj.offers.first().benefit
        return BenefitSerializer(benefit).data

    def get_redeem_url(self, obj):
        url = get_ecommerce_url('/coupons/offer/')
        return '{url}?code={code}'.format(url=url, code=obj.code)

    class Meta(object):
        model = Voucher
        fields = (
            'id', 'name', 'code', 'redeem_url', 'usage', 'start_datetime', 'end_datetime', 'num_basket_additions',
            'num_orders', 'total_discount', 'date_created', 'offers', 'is_available_to_user', 'benefit'
        )


class CategorySerializer(serializers.ModelSerializer):
    # NOTE (CCB): We are explicitly ignoring child categories. They are not relevant to our current needs. Support
    # should be added later, if needed.

    class Meta(object):
        model = Category


class CouponListSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Product
        fields = ('id', 'title',)


class CouponSerializer(ProductPaymentInfoMixin, serializers.ModelSerializer):
    """ Serializer for Coupons. """
    benefit_type = serializers.SerializerMethodField()
    benefit_value = serializers.SerializerMethodField()
    coupon_type = serializers.SerializerMethodField()
    catalog_query = serializers.SerializerMethodField()
    categories = CategorySerializer(many=True, read_only=True)
    client = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    code_status = serializers.SerializerMethodField()
    course_seat_types = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    last_edited = serializers.SerializerMethodField()
    max_uses = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    num_uses = serializers.SerializerMethodField()
    payment_information = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    seats = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    voucher_type = serializers.SerializerMethodField()

    def retrieve_benefit(self, obj):
        """Helper method to retrieve the benefit from voucher. """
        return self.retrieve_voucher(obj).benefit

    def retrieve_end_date(self, obj):
        """Helper method to retrieve the voucher end datetime. """
        return self.retrieve_voucher(obj).end_datetime

    def retrieve_offer(self, obj):
        """Helper method to retrieve the offer from coupon. """
        return self.retrieve_voucher(obj).offers.first()

    def retrieve_start_date(self, obj):
        """Helper method to retrieve the voucher start datetime. """
        return self.retrieve_voucher(obj).start_datetime

    def retrieve_voucher(self, obj):
        """Helper method to retrieve the first voucher from coupon. """
        return obj.attr.coupon_vouchers.vouchers.first()

    def retrieve_voucher_usage(self, obj):
        """Helper method to retrieve usage from voucher. """
        return self.retrieve_voucher(obj).usage

    def retrieve_quantity(self, obj):
        """Helper method to retrieve number from vouchers. """
        return obj.attr.coupon_vouchers.vouchers.count()

    def get_benefit_type(self, obj):
        return self.retrieve_benefit(obj).type

    def get_benefit_value(self, obj):
        return self.retrieve_benefit(obj).value

    def get_coupon_type(self, obj):
        benefit = self.retrieve_benefit(obj)
        if benefit.type == Benefit.PERCENTAGE and benefit.value == 100:
            return _('Enrollment code')
        return _('Discount code')

    def get_catalog_query(self, obj):
        offer = self.retrieve_offer(obj)
        return offer.condition.range.catalog_query

    def get_client(self, obj):
        return Invoice.objects.get(order__basket__lines__product=obj).business_client.name

    def get_code(self, obj):
        if self.retrieve_quantity(obj) == 1:
            return self.retrieve_voucher(obj).code

    def get_code_status(self, obj):
        start_date = self.retrieve_start_date(obj)
        end_date = self.retrieve_end_date(obj)
        current_datetime = timezone.now()
        in_time_interval = (start_date < current_datetime) and (end_date > current_datetime)
        return _('ACTIVE') if in_time_interval else _('INACTIVE')

    def get_course_seat_types(self, obj):
        offer = self.retrieve_offer(obj)
        course_seat_types = offer.condition.range.course_seat_types
        return course_seat_types.split(',') if course_seat_types else course_seat_types

    def get_end_date(self, obj):
        return self.retrieve_end_date(obj)

    def get_last_edited(self, obj):
        history = obj.history.latest()
        return history.history_user.username, history.history_date

    def get_max_uses(self, obj):
        offer = self.retrieve_offer(obj)
        return offer.max_global_applications

    def get_note(self, obj):
        try:
            return obj.attr.note
        except AttributeError:
            return None

    def get_num_uses(self, obj):
        offer = self.retrieve_offer(obj)
        return offer.num_applications

    def get_payment_information(self, obj):
        """
        Retrieve the payment information.
        Currently only invoices are supported, in the event of adding another
        payment processor append it to the response dictionary.
        """
        invoice = Invoice.objects.filter(order__basket__lines__product=obj).first()
        response = {'Invoice': InvoiceSerializer(invoice).data}
        return response

    def get_quantity(self, obj):
        return self.retrieve_quantity(obj)

    def get_seats(self, obj):
        offer = self.retrieve_offer(obj)
        _range = offer.condition.range
        request = self.context['request']
        if _range.catalog:
            stockrecords = _range.catalog.stock_records.all()
            seats = Product.objects.filter(id__in=[sr.product.id for sr in stockrecords])
        else:
            seats = get_seats_from_query(
                request.site,
                _range.catalog_query,
                _range.course_seat_types
            )
        serializer = ProductSerializer(seats, many=True, context={'request': request})
        return serializer.data

    def get_start_date(self, obj):
        return self.retrieve_start_date(obj)

    def get_voucher_type(self, obj):
        return self.retrieve_voucher_usage(obj)

    class Meta(object):
        model = Product
        fields = (
            'benefit_type', 'benefit_value', 'catalog_query', 'categories',
            'client', 'code', 'code_status', 'coupon_type', 'course_seat_types',
            'end_date', 'id', 'last_edited', 'max_uses', 'note',
            'num_uses', 'payment_information', 'price', 'quantity',
            'seats', 'start_date', 'title', 'voucher_type'
        )


class CheckoutSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    payment_form_data = serializers.SerializerMethodField()
    payment_page_url = serializers.URLField()
    payment_processor = serializers.CharField()

    def get_payment_form_data(self, obj):
        return obj['payment_form_data']


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Invoice


class SiteSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Site


class SiteConfigurationSerializer(serializers.ModelSerializer):
    site = SiteSerializer(read_only=True)

    class Meta(object):
        model = SiteConfiguration

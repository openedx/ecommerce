"""Serializers for data manipulated by ecommerce API endpoints."""
from __future__ import unicode_literals

import logging
from datetime import timedelta
from decimal import Decimal

import waffle
from dateutil.parser import parse
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model
from rest_framework import serializers
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings

from ecommerce.core.constants import (
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    COURSE_ID_REGEX,
    ISO_8601_FORMAT,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.courses.models import Course
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.offer.constants import (
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_EMAIL_BOUNCED,
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    OFFER_ASSIGNMENT_REVOKED,
    OFFER_MAX_USES_DEFAULT,
    OFFER_REDEEMED
)
from ecommerce.extensions.offer.utils import (
    send_assigned_offer_email,
    send_assigned_offer_reminder_email,
    send_revoked_offer_email
)
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
BasketLine = get_model('basket', 'Line')
Benefit = get_model('offer', 'Benefit')
BillingAddress = get_model('order', 'BillingAddress')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Line = get_model('order', 'Line')
OfferAssignment = get_model('offer', 'OfferAssignment')
Order = get_model('order', 'Order')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')
ProductCategory = get_model('catalogue', 'ProductCategory')
Refund = get_model('refund', 'Refund')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')
User = get_user_model()

COURSE_DETAIL_VIEW = 'api:v2:course-detail'
PRODUCT_DETAIL_VIEW = 'api:v2:product-detail'


def is_custom_code(obj):
    """Helper method to check if the voucher contains custom code. """
    return not is_enrollment_code(obj) and retrieve_quantity(obj) == 1


def is_enrollment_code(obj):
    benefit = retrieve_voucher(obj).benefit
    return benefit.type == Benefit.PERCENTAGE and benefit.value == 100


def retrieve_benefit(obj):
    """Helper method to retrieve the benefit from voucher. """
    return retrieve_offer(obj).benefit


def retrieve_condition(obj):
    """Helper method to retrieve the benefit from voucher. """
    return retrieve_offer(obj).condition


def retrieve_enterprise_condition(obj):
    """Helper method to retrieve the benefit from voucher. """
    enterprise_offer = retrieve_enterprise_offer(obj)
    return enterprise_offer and enterprise_offer.condition


def retrieve_end_date(obj):
    """Helper method to retrieve the voucher end datetime. """
    return retrieve_voucher(obj).end_datetime


def retrieve_offer(obj):
    """Helper method to retrieve the offer from coupon. """
    return retrieve_voucher(obj).best_offer


def retrieve_original_offer(obj):
    """Helper method to retrieve the offer from coupon. """
    return retrieve_voucher(obj).original_offer


def retrieve_enterprise_offer(obj):
    """Helper method to retrieve the offer from coupon. """
    return retrieve_voucher(obj).enterprise_offer


def retrieve_range(obj):
    """Helper method to retrieve the range from coupon."""
    return retrieve_original_offer(obj).condition.range


def retrieve_quantity(obj):
    """Helper method to retrieve number of vouchers. """
    return obj.attr.coupon_vouchers.vouchers.count()


def retrieve_start_date(obj):
    """Helper method to retrieve the voucher start datetime. """
    return retrieve_voucher(obj).start_datetime


def retrieve_voucher(obj):
    """Helper method to retrieve the first voucher from coupon. """
    return obj.attr.coupon_vouchers.vouchers.first()


def retrieve_all_vouchers(obj):
    """Helper method to retrieve all vouchers from coupon. """
    return obj.attr.coupon_vouchers.vouchers.all()


def retrieve_voucher_usage(obj):
    """Helper method to retrieve usage from voucher. """
    return retrieve_voucher(obj).usage


def _flatten(attrs):
    """Transform a list of attribute names and values into a dictionary keyed on the names."""
    return {attr['name']: attr['value'] for attr in attrs}


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
    billing_address = BillingAddressSerializer(allow_null=True)
    date_placed = serializers.DateTimeField(format=ISO_8601_FORMAT)
    discount = serializers.SerializerMethodField()
    lines = LineSerializer(many=True)
    payment_processor = serializers.SerializerMethodField()
    user = UserSerializer()
    vouchers = serializers.SerializerMethodField()

    def get_vouchers(self, obj):
        try:
            serializer = VoucherSerializer(
                obj.basket.vouchers.all(), many=True, context={'request': self.context['request']}
            )
            return serializer.data
        except (AttributeError, ValueError):
            return None

    def get_payment_processor(self, obj):
        try:
            return obj.sources.all()[0].source_type.name
        except IndexError:
            return None

    def get_discount(self, obj):
        try:
            discount = obj.discounts.all()[0]
            return str(discount.amount)
        except IndexError:
            return '0'

    class Meta(object):
        model = Order
        fields = (
            'billing_address',
            'currency',
            'date_placed',
            'discount',
            'lines',
            'number',
            'payment_processor',
            'status',
            'total_excl_tax',
            'user',
            'vouchers',
        )


class BasketSerializer(serializers.ModelSerializer):
    """Serializer for parsing basket data."""
    owner = UserSerializer()
    products = serializers.SerializerMethodField()
    vouchers = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_processor = serializers.SerializerMethodField()

    def get_vouchers(self, obj):
        try:
            serializer = VoucherSerializer(
                obj.vouchers.all(), many=True, context={'request': self.context['request']}
            )
            return serializer.data
        except (AttributeError, ValueError):
            return None

    def get_payment_status(self, obj):
        successful_payment_notifications = obj.paymentprocessorresponse_set.filter(
            Q(response__contains='ACCEPT') | Q(response__contains='approved')
        )
        if successful_payment_notifications:
            return "Accepted"
        return "Declined"

    def get_payment_processor(self, obj):
        payment_notifications = obj.paymentprocessorresponse_set.filter(transaction_id__isnull=False)
        if payment_notifications:
            return payment_notifications[0].processor_name
        return "None"

    def get_products(self, obj):
        lines = BasketLine.objects.filter(basket=obj)
        products = [line.product for line in lines]
        serialized_data = []
        for product in products:

            serialized_data.append(ProductAttributeValueSerializer(
                product.attr,
                many=True,
                read_only=True,
                context={'request': self.context['request']}
            ).data)
        # return serializer.data
        # serializer = ProductSerializer(products, many=True, context={'request': self.context['request']})
        return serialized_data

    class Meta(object):
        model = Basket
        fields = (
            'id',
            'status',
            'owner',
            'order_number',
            'products',
            'vouchers',
            'payment_status',
            'payment_processor',
        )


class PaymentProcessorSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """ Serializer to use with instances of processors.BasePaymentProcessor """

    def to_representation(self, instance):
        """ Serialize instances as a string instead of a mapping object. """
        return instance.NAME


class RefundSerializer(serializers.ModelSerializer):
    """ Serializer for Refund objects. """

    class Meta(object):
        model = Refund
        fields = '__all__'


class CourseSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.RegexField(COURSE_ID_REGEX, max_length=255)
    products = ProductSerializer(many=True)
    products_url = serializers.SerializerMethodField()
    last_edited = serializers.SerializerMethodField()
    has_active_bulk_enrollment_code = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super(CourseSerializer, self).__init__(*args, **kwargs)

        # NOTE: All normal initializations of the serializer will include a context kwarg.
        # We use dict.get() here because Swagger does not include context when generating docs.
        include_products = kwargs.get('context', {}).pop('include_products', False)
        if not include_products:
            self.fields.pop('products', None)

    def get_last_edited(self, obj):
        return obj.modified.strftime(ISO_8601_FORMAT) if obj.modified else None

    def get_products_url(self, obj):
        return reverse('api:v2:course-product-list', kwargs={'parent_lookup_course_id': obj.id},
                       request=self.context['request'])

    def get_has_active_bulk_enrollment_code(self, obj):
        return True if obj.enrollment_code_product else False

    class Meta(object):
        model = Course
        fields = (
            'id', 'url', 'name', 'verification_deadline', 'type',
            'products_url', 'last_edited', 'products', 'has_active_bulk_enrollment_code')
        read_only_fields = ('type', 'products', 'site')
        extra_kwargs = {
            'url': {'view_name': COURSE_DETAIL_VIEW}
        }


class EntitlementProductHelper(object):
    @staticmethod
    def validate(product):
        attrs = _flatten(product['attribute_values'])

        if 'certificate_type' not in attrs:
            raise serializers.ValidationError(_(u"Products must have a certificate type."))

        if 'price' not in product:
            raise serializers.ValidationError(_(u"Products must have a price."))

    @staticmethod
    def save(partner, course, uuid, product):
        attrs = _flatten(product['attribute_values'])

        if not uuid:
            raise Exception(_(u"You need to provide a course UUID to create Course Entitlements."))

        # Extract arguments required for Seat creation, deserializing as necessary.
        certificate_type = attrs.get('certificate_type')
        price = Decimal(product['price'])

        create_or_update_course_entitlement(
            certificate_type,
            price,
            partner,
            uuid,
            course.name
        )


class SeatProductHelper(object):
    @staticmethod
    def validate(product):
        attrs = _flatten(product['attribute_values'])
        if attrs.get('id_verification_required') is None:
            raise serializers.ValidationError(_(u"Products must indicate whether ID verification is required."))

        # Verify that a price is present.
        if product.get('price') is None:
            raise serializers.ValidationError(_(u"Products must have a price."))

    @staticmethod
    def save(course, product, create_enrollment_code):
        attrs = _flatten(product['attribute_values'])

        # Extract arguments required for Seat creation, deserializing as necessary.
        certificate_type = attrs.get('certificate_type', '')
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
            expires=expires,
            credit_provider=credit_provider,
            credit_hours=credit_hours,
            create_enrollment_code=create_enrollment_code
        )


class AtomicPublicationSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for saving and publishing a Course and associated products.

    Using a ModelSerializer for the Course data makes it difficult to use this serializer to handle updates.
    The automatically applied validation logic rejects course IDs which already exist in the database.
    """
    id = serializers.RegexField(COURSE_ID_REGEX, max_length=255)
    uuid = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=255)

    # Verification deadline should only be required if the course actually requires verification.
    verification_deadline = serializers.DateTimeField(required=False, allow_null=True)
    products = serializers.ListField()

    def __init__(self, *args, **kwargs):
        super(AtomicPublicationSerializer, self).__init__(*args, **kwargs)
        self.partner = kwargs['context'].pop('partner', None)

    def validate_products(self, products):
        """Validate product data."""
        for product in products:
            product_class = product.get('product_class')

            if product_class == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
                EntitlementProductHelper.validate(product)
            elif product_class == SEAT_PRODUCT_CLASS_NAME:
                SeatProductHelper.validate(product)
            else:
                raise serializers.ValidationError(
                    _(u"Invalid product class [{product_class}] requested.").format(product_class=product_class)
                )

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
        course_uuid = self.validated_data.get('uuid')
        course_name = self.validated_data['name']
        course_verification_deadline = self.validated_data.get('verification_deadline')
        # ENT-803: by default enable enrollment code creation
        create_or_activate_enrollment_code = True
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
                site = self.context['request'].site
                course, created = Course.objects.get_or_create(
                    id=course_id, partner=site.siteconfiguration.partner
                )
                course.name = course_name
                course.verification_deadline = course_verification_deadline
                course.save()

                for product in products:
                    product_class = product.get('product_class')

                    if product_class == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
                        EntitlementProductHelper.save(partner, course, course_uuid, product)
                    elif product_class == SEAT_PRODUCT_CLASS_NAME:
                        SeatProductHelper.save(course, product, create_or_activate_enrollment_code)

                if course.get_enrollment_code():
                    course.toggle_enrollment_code_status(is_active=create_or_activate_enrollment_code)

                resp_message = course.publish_to_lms()
                published = (resp_message is None)

                if published:
                    return created, None, None
                else:
                    raise Exception(resp_message)

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(u'Failed to save and publish [%s]: [%s]', course_id, e.message)
            return False, e, e.message


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
        benefit = obj.best_offer.benefit
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


class CodeUsageSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    code = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    redeem_url = serializers.SerializerMethodField()
    redemptions = serializers.SerializerMethodField()

    def get_code(self, obj):
        return obj.get('code')

    def get_redeem_url(self, obj):
        url = get_ecommerce_url('/coupons/offer/')
        return '{url}?code={code}'.format(url=url, code=self.get_code(obj))

    def get_assigned_to(self, obj):
        return obj.get('user_email')

    def get_redemptions(self, obj):
        voucher = Voucher.objects.get(code=self.get_code(obj))
        offer = voucher.best_offer
        redemption_count = voucher.num_orders

        if voucher.usage == Voucher.SINGLE_USE:
            max_coupon_usage = 1
        elif offer.max_global_applications is None:
            max_coupon_usage = OFFER_MAX_USES_DEFAULT
        else:
            max_coupon_usage = offer.max_global_applications

        return {
            'used': redemption_count,
            'total': max_coupon_usage,
        }


class NotAssignedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_assigned_to(self, obj):
        return ''


class NotRedeemedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_redemptions(self, obj):
        usage_type = self.context.get('usage_type')
        if usage_type in (Voucher.SINGLE_USE, Voucher.MULTI_USE_PER_CUSTOMER):
            return super(NotRedeemedCodeUsageSerializer, self).get_redemptions(obj)
        else:
            num_assignments = OfferAssignment.objects.filter(
                code=self.get_code(obj),
                user_email=self.get_assigned_to(obj),
                status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING],
            ).count()
            return {'used': 0, 'total': num_assignments}


class PartialRedeemedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_redemptions(self, obj):
        usage_type = self.context.get('usage_type')
        if usage_type == Voucher.SINGLE_USE:
            return {}
        elif usage_type == Voucher.MULTI_USE_PER_CUSTOMER:
            return super(PartialRedeemedCodeUsageSerializer, self).get_redemptions(obj)
        else:
            num_assignments = OfferAssignment.objects.filter(
                code=self.get_code(obj),
                user_email=self.get_assigned_to(obj),
                status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING],
            ).count()
            num_applications = VoucherApplication.objects.filter(
                voucher__code=self.get_code(obj),
                user__email=self.get_assigned_to(obj)
            ).count()
            return {'used': num_applications, 'total': num_assignments + num_applications}


class RedeemedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_code(self, obj):
        return obj.get('voucher__code')

    def get_assigned_to(self, obj):
        return obj.get('user__email')

    def get_redemptions(self, obj):
        num_applications = VoucherApplication.objects.filter(
            voucher__code=self.get_code(obj),
            user__email=self.get_assigned_to(obj)
        ).count()
        return {'used': num_applications, 'total': num_applications}


class CategorySerializer(serializers.ModelSerializer):
    # NOTE (CCB): We are explicitly ignoring child categories. They are not relevant to our current needs. Support
    # should be added later, if needed.

    class Meta(object):
        model = Category
        fields = ('id', 'name',)


class CouponListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()

    def get_category(self, obj):
        category = ProductCategory.objects.filter(product=obj).first().category
        return CategorySerializer(category).data

    def get_client(self, obj):
        return Invoice.objects.get(order__lines__product=obj).business_client.name

    def get_code(self, obj):
        if is_custom_code(obj):
            return retrieve_voucher(obj).code

    class Meta(object):
        model = Product
        fields = ('category', 'client', 'code', 'id', 'title', 'date_created')


class EnterpriseCouponOverviewListSerializer(serializers.ModelSerializer):
    """
    Serializer for Enterprise Coupons list overview.
    """
    end_date = serializers.SerializerMethodField()
    has_error = serializers.SerializerMethodField()
    max_uses = serializers.SerializerMethodField()
    num_codes = serializers.SerializerMethodField()
    num_unassigned = serializers.SerializerMethodField()
    num_uses = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    usage_limitation = serializers.SerializerMethodField()

    def get_num_unassigned(self, coupon):
        """
        Returns number of unassigned vouchers. These are the vouchers that have
        at-least 1 potential slot available for asssignment.
        """
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        num_unassigned = len([
            voucher.code
            for voucher in vouchers
            if voucher.slots_available_for_assignment > 0
        ])
        return num_unassigned

    def get_has_error(self, obj):
        """
        Returns True if any assignment associated with coupon is having
        error, otherwise False.
        """
        offer = retrieve_offer(obj)
        offer_assignments_with_error = offer.offerassignment_set.filter(
            status=OFFER_ASSIGNMENT_EMAIL_BOUNCED
        )
        return offer_assignments_with_error.exists()

    # Max number of codes available (Maximum Coupon Usage).
    def get_max_uses(self, obj):
        voucher_usage = retrieve_voucher_usage(obj)
        offer = retrieve_offer(obj)
        max_uses_per_code = None
        if voucher_usage == Voucher.SINGLE_USE:
            max_uses_per_code = 1
        elif offer.max_global_applications:
            max_uses_per_code = offer.max_global_applications
        else:
            max_uses_per_code = OFFER_MAX_USES_DEFAULT

        return max_uses_per_code * retrieve_quantity(obj)

    # Redemption count.
    def get_num_uses(self, obj):
        vouchers = retrieve_all_vouchers(obj)
        num_uses = 0
        for voucher in vouchers:
            num_uses += voucher.num_orders
        return num_uses

    # Number of codes.
    def get_num_codes(self, obj):
        return retrieve_quantity(obj)

    # Usage Limitation (Maximum # of usages per code).
    def get_usage_limitation(self, obj):
        return retrieve_voucher_usage(obj)

    def get_start_date(self, obj):
        return retrieve_start_date(obj)

    def get_end_date(self, obj):
        return retrieve_end_date(obj)

    class Meta(object):
        model = Product
        fields = (
            'end_date', 'has_error', 'id', 'max_uses', 'num_codes', 'num_unassigned',
            'num_uses', 'start_date', 'title', 'usage_limitation'
        )


class EnterpriseCouponListSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    enterprise_customer = serializers.SerializerMethodField()
    enterprise_customer_catalog = serializers.SerializerMethodField()
    code_status = serializers.SerializerMethodField()

    def get_client(self, obj):
        return Invoice.objects.get(order__lines__product=obj).business_client.name

    def get_enterprise_customer(self, obj):
        """ Get the Enterprise Customer UUID attached to a coupon. """
        offer_condition = retrieve_enterprise_condition(obj)
        return offer_condition and offer_condition.enterprise_customer_uuid

    def get_enterprise_customer_catalog(self, obj):
        """ Get the Enterprise Customer Catalog UUID attached to a coupon. """
        offer_condition = retrieve_enterprise_condition(obj)
        return offer_condition and offer_condition.enterprise_customer_catalog_uuid

    def get_code_status(self, obj):
        start_date = retrieve_start_date(obj)
        end_date = retrieve_end_date(obj)
        current_datetime = timezone.now()
        in_time_interval = start_date < current_datetime < end_date
        return _('ACTIVE') if in_time_interval else _('INACTIVE')

    class Meta(object):
        model = Product
        fields = (
            'client',
            'code_status',
            'enterprise_customer',
            'enterprise_customer_catalog',
            'id',
            'title',
            'date_created',
        )


class CouponSerializer(ProductPaymentInfoMixin, serializers.ModelSerializer):
    """ Serializer for Coupons. """
    benefit_type = serializers.SerializerMethodField()
    benefit_value = serializers.SerializerMethodField()
    catalog_query = serializers.SerializerMethodField()
    course_catalog = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    code_status = serializers.SerializerMethodField()
    coupon_type = serializers.SerializerMethodField()
    course_seat_types = serializers.SerializerMethodField()
    email_domains = serializers.SerializerMethodField()
    enterprise_customer = serializers.SerializerMethodField()
    enterprise_customer_catalog = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    last_edited = serializers.SerializerMethodField()
    max_uses = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    notify_email = serializers.SerializerMethodField()
    num_uses = serializers.SerializerMethodField()
    payment_information = serializers.SerializerMethodField()
    program_uuid = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    seats = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    voucher_type = serializers.SerializerMethodField()

    def get_benefit_type(self, obj):
        return retrieve_benefit(obj).type or getattr(retrieve_benefit(obj).proxy(), 'benefit_class_type', None)

    def get_benefit_value(self, obj):
        return retrieve_benefit(obj).value

    def get_catalog_query(self, obj):
        offer_range = retrieve_range(obj)
        return offer_range.catalog_query if offer_range else None

    def get_course_catalog(self, obj):
        offer_range = retrieve_range(obj)
        return offer_range.course_catalog if offer_range else None

    def get_category(self, obj):
        category = ProductCategory.objects.filter(product=obj).first().category
        return CategorySerializer(category).data

    def get_coupon_type(self, obj):
        if is_enrollment_code(obj):
            return _('Enrollment code')
        return _('Discount code')

    def get_client(self, obj):
        return Invoice.objects.get(order__lines__product=obj).business_client.name

    def get_code(self, obj):
        if retrieve_quantity(obj) == 1:
            return retrieve_voucher(obj).code

    def get_code_status(self, obj):
        start_date = retrieve_start_date(obj)
        end_date = retrieve_end_date(obj)
        current_datetime = timezone.now()
        in_time_interval = start_date < current_datetime < end_date
        return _('ACTIVE') if in_time_interval else _('INACTIVE')

    def get_course_seat_types(self, obj):
        seat_types = []
        offer_range = retrieve_range(obj)

        if offer_range:
            course_seat_types = offer_range.course_seat_types or ''
            seat_types = course_seat_types.split(',')

        return seat_types

    def get_email_domains(self, obj):
        offer = retrieve_offer(obj)
        return offer.email_domains

    def get_end_date(self, obj):
        return retrieve_end_date(obj)

    def get_enterprise_customer(self, obj):
        """ Get the Enterprise Customer UUID attached to a coupon. """
        offer_range = retrieve_range(obj)
        offer_condition = retrieve_condition(obj)
        if offer_range and offer_range.enterprise_customer:
            return offer_range.enterprise_customer
        elif offer_condition.enterprise_customer_uuid:
            return offer_condition.enterprise_customer_uuid
        else:
            return None

    def get_enterprise_customer_catalog(self, obj):
        """ Get the Enterprise Customer Catalog UUID attached to a coupon. """
        offer_range = retrieve_range(obj)
        offer_condition = retrieve_condition(obj)
        if offer_range and offer_range.enterprise_customer_catalog:
            return offer_range.enterprise_customer_catalog
        elif offer_condition.enterprise_customer_catalog_uuid:
            return offer_condition.enterprise_customer_catalog_uuid
        else:
            return None

    def get_last_edited(self, obj):
        return None, obj.date_updated

    def get_max_uses(self, obj):
        offer = retrieve_offer(obj)
        return offer.max_global_applications

    def get_note(self, obj):
        try:
            return obj.attr.note
        except AttributeError:
            return None

    def get_notify_email(self, obj):
        try:
            return obj.attr.notify_email
        except AttributeError:
            return None

    def get_num_uses(self, obj):
        offer = retrieve_offer(obj)
        return offer.num_applications

    def get_program_uuid(self, obj):
        """ Get the Program UUID attached to the coupon. """
        return retrieve_offer(obj).condition.program_uuid

    def get_payment_information(self, obj):
        """
        Retrieve the payment information.
        Currently only invoices are supported, in the event of adding another
        payment processor append it to the response dictionary.
        """
        invoice = Invoice.objects.filter(order__lines__product=obj).first()
        response = {'Invoice': InvoiceSerializer(invoice).data}
        return response

    def get_quantity(self, obj):
        return retrieve_quantity(obj)

    def get_start_date(self, obj):
        return retrieve_start_date(obj)

    def get_seats(self, obj):
        offer_range = retrieve_range(obj)
        request = self.context['request']

        if offer_range and offer_range.catalog:
            stockrecords = offer_range.catalog.stock_records.all()
            seats = Product.objects.filter(id__in=[sr.product.id for sr in stockrecords])
            serializer = ProductSerializer(seats, many=True, context={'request': request})
            return serializer.data

        return {}

    def get_voucher_type(self, obj):
        return retrieve_voucher_usage(obj)

    class Meta(object):
        model = Product
        fields = (
            'benefit_type', 'benefit_value', 'catalog_query', 'course_catalog', 'category',
            'client', 'code', 'code_status', 'coupon_type', 'course_seat_types',
            'email_domains', 'end_date', 'enterprise_customer', 'enterprise_customer_catalog',
            'id', 'last_edited', 'max_uses', 'note', 'notify_email', 'num_uses', 'payment_information',
            'program_uuid', 'price', 'quantity', 'seats', 'start_date', 'title', 'voucher_type'
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
        fields = '__all__'


class ProviderSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    description = serializers.CharField()
    display_name = serializers.CharField()
    enable_integration = serializers.BooleanField()
    fulfillment_instructions = serializers.CharField()
    id = serializers.CharField()
    status_url = serializers.CharField()
    thumbnail_url = serializers.CharField()
    url = serializers.CharField()


class OfferAssignmentSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = OfferAssignment
        fields = ('id', 'user_email', 'code')


class CouponCodeAssignmentSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    codes = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    emails = serializers.ListField(
        child=serializers.EmailField(), required=True, write_only=True
    )
    offer_assignments = serializers.ListField(
        child=OfferAssignmentSerializer(), read_only=True
    )

    def create(self, validated_data):
        """Create OfferAssignment objects for each email and the available_assignments determined from validation."""
        emails = validated_data.get('emails')
        voucher_usage_type = validated_data.pop('voucher_usage_type')
        email_template = validated_data.pop('template')
        available_assignments = validated_data.pop('available_assignments')
        email_iterator = iter(emails)
        offer_assignments = []
        emails_already_sent = set()

        for code in available_assignments:
            offer = available_assignments[code]['offer']
            email = next(email_iterator) if voucher_usage_type == Voucher.MULTI_USE_PER_CUSTOMER else None
            for _ in range(available_assignments[code]['num_slots']):
                new_offer_assignment = OfferAssignment.objects.create(
                    offer=offer,
                    code=code,
                    user_email=email or next(email_iterator),
                )
                offer_assignments.append(new_offer_assignment)
                # Start async email task. For MULTI_USE_PER_CUSTOMER, a single email is sent
                email_code_pair = frozenset((new_offer_assignment.user_email, new_offer_assignment.code))
                if email_code_pair not in emails_already_sent:
                    self._trigger_email_sending_task(email_template, new_offer_assignment, voucher_usage_type)
                    emails_already_sent.add(email_code_pair)

        validated_data['offer_assignments'] = offer_assignments
        return validated_data

    def validate(self, data):
        """
        Validate that the given emails can be assigned to a slot in the coupon, to the codes if specified.
        A slot is a potential redemption of a voucher contained within the top level Coupon.
        """
        codes = data.get('codes')
        emails = data.get('emails')
        coupon = self.context.get('coupon')
        template = self.context.get('template')
        available_assignments = {}
        vouchers = coupon.attr.coupon_vouchers.vouchers

        # Limit which vouchers to consider for assignment by the codes passed in.
        if codes:
            vouchers = vouchers.filter(code__in=codes)

        # For ONCE_PER_CUSTOMER Coupons, exclude vouchers that have already
        # been assigned to or redeemed by the requested emails.
        voucher_usage_type = vouchers.first().usage
        if voucher_usage_type == Voucher.ONCE_PER_CUSTOMER:
            existing_assignments_for_users = OfferAssignment.objects.filter(user_email__in=emails).exclude(
                status__in=OFFER_ASSIGNMENT_REVOKED
            )
            existing_applications_for_users = VoucherApplication.objects.filter(user__email__in=emails)
            codes_to_exclude = (
                [assignment.code for assignment in existing_assignments_for_users] +
                [application.voucher.code for application in existing_applications_for_users]
            )
            emails_requiring_exclusions = (
                [assignment.user_email for assignment in existing_assignments_for_users] +
                [application.user.email for application in existing_applications_for_users]
            )
            logger.info(
                'Excluding the following codes because they have been assigned to or redeemed by '
                'at least one user in the given list of emails to assign to this coupon. '
                'codes: %s, emails: %s, coupon_id: %s', codes_to_exclude, emails_requiring_exclusions, coupon.id
            )
            vouchers = vouchers.exclude(code__in=codes_to_exclude)

        total_slots = 0
        for voucher in vouchers.all():
            available_slots = voucher.slots_available_for_assignment
            # If there are no available slots for this voucher, skip it.
            if available_slots < 1:
                continue

            if voucher_usage_type != Voucher.MULTI_USE_PER_CUSTOMER:
                available_slots = min(available_slots, len(emails) - total_slots)

            # If there are available slots, and we still have slots to fill,
            # add information to the available_assignments dict.
            if total_slots < len(emails):
                # Keep track of which codes can be assigned how many times
                # along with its corresponding ConditionalOffer.
                available_assignments[voucher.code] = {'offer': voucher.enterprise_offer, 'num_slots': available_slots}

                # For Multi use per customer vouchers, all of the slots must go to one user email,
                # so for accounting purposes we only count one slot here towards the total.
                if voucher_usage_type == Voucher.MULTI_USE_PER_CUSTOMER:
                    total_slots += 1
                else:
                    total_slots += available_slots
            else:
                break
        # If we got through all the vouchers and don't have enough slots for the emails given, the request isn't valid.
        if total_slots < len(emails):
            raise serializers.ValidationError('Not enough available codes for assignment!')

        # Add available_assignments to the validated data so that we can perform the assignments in create.
        data['voucher_usage_type'] = voucher_usage_type
        data['available_assignments'] = available_assignments
        data['template'] = template
        return data

    def _trigger_email_sending_task(self, template, assigned_offer, voucher_usage_type):
        """
        Schedule async task to send email to the learner who has been assigned the code.
        """
        code_expiration_date = assigned_offer.created + timedelta(days=365)
        redemptions_remaining = (
            assigned_offer.offer.max_global_applications if voucher_usage_type == Voucher.MULTI_USE_PER_CUSTOMER else 1
        )
        try:
            send_assigned_offer_email(
                template=template,
                offer_assignment_id=assigned_offer.id,
                learner_email=assigned_offer.user_email,
                code=assigned_offer.code,
                redemptions_remaining=redemptions_remaining,
                code_expiration_date=code_expiration_date.strftime('%d %B,%Y')
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                '[Offer Assignment] Email for offer_assignment_id: %d raised exception: %r', assigned_offer.id, exc)


class CouponCodeRevokeRemindBulkSerializer(serializers.ListSerializer):  # pylint: disable=abstract-method

    def to_internal_value(self, data):
        """
        This implements the same relevant logic as ListSerializer except that if one or more items fail validation,
        processing for other items that did not fail will continue.
        """

        if not isinstance(data, list):
            message = self.error_messages['not_a_list'].format(
                input_type=type(data).__name__
            )
            raise serializers.ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            })

        ret = []

        for item in data:
            try:
                validated = self.child.run_validation(item)
            except serializers.ValidationError as exc:
                ret.append(
                    {
                        'non_field_errors': [{
                            'code': item.get('code'),
                            'email': item.get('email'),
                            'detail': 'failure',
                            'message': exc.detail['non_field_errors'][0]
                        }]
                    }
                )
            else:
                ret.append(validated)

        return ret

    def create(self, validated_data):
        """
        This selectively calls the child create method based on whether or not validation failed for each payload.
        """
        ret = []
        for attrs in validated_data:
            if 'non_field_errors' not in attrs and not any(isinstance(attrs[field], list) for field in attrs):
                ret.append(self.child.create(attrs))
            else:
                ret.append(attrs)

        return ret

    def to_representation(self, data):
        """
        This selectively calls to_representation on each result that was processed by create.
        """
        response = []
        for item in data:
            if 'detail' in item:
                response.append(self.child.to_representation(item))
            elif 'non_field_errors' in item:
                response.append(item['non_field_errors'][0])
            else:
                response.append(item)

        return response


class CouponCodeMixin(object):

    def validate_coupon_has_code(self, coupon, code):
        """
        Validate that the code is associated with the coupon
        :param coupon: (Product): Coupon product associated with vouchers
        :param code: (str): Code associated with the voucher
        :raises rest_framework.exceptions.ValidationError in case code is not associated with the coupon
        """
        if not coupon.attr.coupon_vouchers.vouchers.filter(code=code).exists():
            raise serializers.ValidationError('Code {} is not associated with this Coupon'.format(code))

    def get_unredeemed_offer_assignments(self, code, email):
        """
        Returns offer assignments associated with the code and email
        :param code: (str): Code associated with the voucher
        :param email: (str): Learner email
        :return: QuerySet containing offer assignments associated with the code and email
        """
        return OfferAssignment.objects.filter(
            code=code,
            user_email=email,
            status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING]
        )


class CouponCodeRevokeSerializer(CouponCodeMixin, serializers.Serializer):  # pylint: disable=abstract-method

    class Meta:  # pylint: disable=old-style-class
        list_serializer_class = CouponCodeRevokeRemindBulkSerializer

    code = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    detail = serializers.CharField(read_only=True)

    def create(self, validated_data):
        """
        Update OfferAssignments to have Revoked status.
        """
        offer_assignments = validated_data.get('offer_assignments')
        email = validated_data.get('email')
        code = validated_data.get('code')
        template = self.context.get('template')
        detail = 'success'

        try:
            for offer_assignment in offer_assignments:
                offer_assignment.status = OFFER_ASSIGNMENT_REVOKED
                offer_assignment.save()

            if template:
                send_revoked_offer_email(
                    template=template,
                    learner_email=email,
                    code=code
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception('Encountered error when revoking code %s for user %s', code, email)
            detail = unicode(exc)

        validated_data['detail'] = detail
        return validated_data

    def validate(self, data):
        """
        Validate that the code is part of the Coupon and the provided code and email have an active OfferAssignment.
        """
        code = data.get('code')
        email = data.get('email')
        coupon = self.context.get('coupon')
        self.validate_coupon_has_code(coupon, code)
        offer_assignments = self.get_unredeemed_offer_assignments(code, email)
        if not offer_assignments.exists():
            raise serializers.ValidationError('No assignments exist for user {} and code {}'.format(email, code))
        data['offer_assignments'] = offer_assignments
        return data


class CouponCodeRemindSerializer(CouponCodeMixin, serializers.Serializer):  # pylint: disable=abstract-method

    class Meta:  # pylint: disable=old-style-class
        list_serializer_class = CouponCodeRevokeRemindBulkSerializer

    code = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    detail = serializers.CharField(read_only=True)

    def create(self, validated_data):
        """
        Send remind email(s) for pending OfferAssignments.
        """
        offer_assignments = validated_data.get('offer_assignments')
        email = validated_data.get('email')
        code = validated_data.get('code')
        redeemed_offer_count = validated_data.get('redeemed_offer_count')
        total_offer_count = validated_data.get('total_offer_count')
        template = self.context.get('template')
        detail = 'success'

        try:
            self._trigger_email_sending_task(
                template,
                offer_assignments.first(),
                redeemed_offer_count,
                total_offer_count
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception('Encountered error during reminder email for code %s of user %s', code, email)
            detail = unicode(exc)

        validated_data['detail'] = detail
        return validated_data

    def validate(self, data):
        """
        Validate that the code is part of the Coupon the code and email provided have an active OfferAssignment.
        """
        code = data.get('code')
        email = data.get('email')
        coupon = self.context.get('coupon')
        self.validate_coupon_has_code(coupon, code)
        offer_assignments = self.get_unredeemed_offer_assignments(code, email)
        offer_assignments_redeemed = OfferAssignment.objects.filter(
            code=code,
            user_email=email,
            status=OFFER_REDEEMED
        )
        if not offer_assignments.exists():
            raise serializers.ValidationError('No assignments exist for user {} and code {}'.format(email, code))
        data['offer_assignments'] = offer_assignments
        data['redeemed_offer_count'] = offer_assignments_redeemed.count()
        data['total_offer_count'] = offer_assignments.count()
        return data

    def _trigger_email_sending_task(self, template, assigned_offer, redeemed_offer_count, total_offer_count):
        """
        Schedule async task to send email to the learner who has been assigned the code.
        """
        code_expiration_date = assigned_offer.created + timedelta(days=365)
        send_assigned_offer_reminder_email(
            template=template,
            learner_email=assigned_offer.user_email,
            code=assigned_offer.code,
            redeemed_offer_count=redeemed_offer_count,
            total_offer_count=total_offer_count,
            code_expiration_date=code_expiration_date.strftime('%d %B,%Y')
        )

"""Serializers for data manipulated by ecommerce API endpoints."""

import logging
import re
from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urljoin

import bleach
import waffle
from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum, prefetch_related_objects
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from opaque_keys.edx.keys import CourseKey
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
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.coupons.utils import is_coupon_available
from ecommerce.courses.models import Course
from ecommerce.enterprise.benefits import BENEFIT_MAP as ENTERPRISE_BENEFIT_MAP
from ecommerce.enterprise.conditions import sum_user_discounts_for_offer
from ecommerce.enterprise.constants import (
    ENTERPRISE_SALES_FORCE_ID_REGEX,
    ENTERPRISE_SALESFORCE_OPPORTUNITY_LINE_ITEM_REGEX
)
from ecommerce.enterprise.utils import (
    calculate_remaining_offer_balance,
    generate_offer_display_name,
    get_enterprise_customer_reply_to_email,
    get_enterprise_customer_sender_alias,
    get_enterprise_customer_uuid_from_voucher
)
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.api.v2.constants import (
    ENABLE_HOIST_ORDER_HISTORY,
    REFUND_ORDER_EMAIL_CLOSING,
    REFUND_ORDER_EMAIL_GREETING,
    REFUND_ORDER_EMAIL_SUBJECT
)
from ecommerce.extensions.catalogue.utils import attach_vouchers_to_coupon_product
from ecommerce.extensions.checkout.views import ReceiptResponseView
from ecommerce.extensions.offer.constants import (
    ASSIGN,
    AUTOMATIC_EMAIL,
    MANUAL_EMAIL,
    OFFER_ASSIGNED,
    OFFER_ASSIGNMENT_EMAIL_BOUNCED,
    OFFER_ASSIGNMENT_EMAIL_PENDING,
    OFFER_ASSIGNMENT_EMAIL_SUBJECT_LIMIT,
    OFFER_ASSIGNMENT_EMAIL_TEMPLATE_FIELD_LIMIT,
    OFFER_ASSIGNMENT_REVOKED,
    OFFER_MAX_USES_DEFAULT,
    OFFER_REDEEMED,
    REMIND,
    REVOKE
)
from ecommerce.extensions.offer.utils import (
    get_benefit_type,
    send_assigned_offer_email,
    send_assigned_offer_reminder_email,
    send_revoked_offer_email
)
from ecommerce.extensions.voucher.utils import create_enterprise_vouchers
from ecommerce.invoice.models import Invoice
from ecommerce.programs.custom import class_path

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
BasketLine = get_model('basket', 'Line')
Benefit = get_model('offer', 'Benefit')
BillingAddress = get_model('order', 'BillingAddress')
Catalog = get_model('catalogue', 'Catalog')
CodeAssignmentNudgeEmails = get_model('offer', 'CodeAssignmentNudgeEmails')
Category = get_model('catalogue', 'Category')
Line = get_model('order', 'Line')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferAssignment = get_model('offer', 'OfferAssignment')
OfferAssignmentEmailTemplates = get_model('offer', 'OfferAssignmentEmailTemplates')
TemplateFileAttachment = get_model('offer', 'TemplateFileAttachment')
OfferAssignmentEmailSentRecord = get_model('offer', 'OfferAssignmentEmailSentRecord')
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
    benefit_type = get_benefit_type(benefit)
    return benefit_type == Benefit.PERCENTAGE and benefit.value == 100


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


def retrieve_enterprise_customer_catalog(coupon):
    """
    Helper method to retrieve the Enterprise Customer Catalog UUID
    attached to a given coupon.
    """
    offer_range = retrieve_range(coupon)
    offer_condition = retrieve_condition(coupon)
    if offer_range and offer_range.enterprise_customer_catalog:
        return offer_range.enterprise_customer_catalog
    if offer_condition.enterprise_customer_catalog_uuid:
        return offer_condition.enterprise_customer_catalog_uuid
    return None


def _flatten(attrs):
    """Transform a list of attribute names and values into a dictionary keyed on the names."""
    return {attr['name']: attr['value'] for attr in attrs}


def create_offer_assignment_email_sent_record(
        enterprise_customer_uuid,
        email_type,
        template=None,
        code=None,
        user_email=None,
        receiver_id=None,
        sender_id=None,
):
    """
    Helper method to save an entry in OfferAssignmentEmailSentRecord when an email is sent.
    Arguments:
        enterprise_customer_uuid (str): UUID of enterprise customer
        email_type (str): the type of email sent e:g ASSIGN, REMIND, REVOKE
        template (OfferAssignmentEmailTemplates): The template used to send the email
        code (str): The voucher code used in the email
        user_email (str): The email of the learner to whom the email was sent
        receiver_id (str): lms_user_id of the receiver, None if pending user
        sender_id (str): lms_user_id of the admin who sent the email

    """
    sender_category = MANUAL_EMAIL if sender_id else AUTOMATIC_EMAIL

    OfferAssignmentEmailSentRecord.create_email_record(
        enterprise_customer_uuid=enterprise_customer_uuid,
        email_type=email_type,
        template=template,
        sender_category=sender_category,
        code=code,
        user_email=user_email,
        receiver_id=receiver_id,
        sender_id=sender_id
    )


class CouponMixin:
    """ Mixin class used for Coupon Serializers using model Product having COUPON Product Class"""

    def get_code_status(self, coupon):
        """retrieve the code_status from coupon Product. """
        start_date = retrieve_start_date(coupon)
        end_date = retrieve_end_date(coupon)
        current_datetime = timezone.now()
        in_time_interval = start_date < current_datetime < end_date
        try:
            inactive = coupon.attr.inactive
        except AttributeError:
            inactive = False

        if not in_time_interval:
            return _('EXPIRED')
        if inactive:
            return _('INACTIVE')
        return _('ACTIVE')


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

    class Meta:
        model = BillingAddress
        fields = ('first_name', 'last_name', 'line1', 'line2', 'postcode', 'state', 'country', 'city')


class UserSerializer(serializers.ModelSerializer):
    """Serializes user information. """

    class Meta:
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

    def get_value(self, dictionary):
        if dictionary.attribute.name == 'Coupon vouchers':
            request = self.context.get('request')
            vouchers = dictionary.value.vouchers.all()
            serializer = VoucherSerializer(vouchers, many=True, context={'request': request})
            return serializer.data
        return dictionary.value

    class Meta:
        model = ProductAttributeValue
        fields = ('name', 'code', 'value',)


class StockRecordSerializer(serializers.ModelSerializer):
    """ Serializer for stock record objects. """

    class Meta:
        model = StockRecord
        fields = ('id', 'product', 'partner', 'partner_sku', 'price_currency', 'price_excl_tax',)


class PartialStockRecordSerializerForUpdate(StockRecordSerializer):
    """ Stock record objects serializer for PUT requests.

    Allowed fields to update are 'price_currency' and 'price_excl_tax'.
    """

    class Meta:
        model = StockRecord
        fields = ('price_currency', 'price_excl_tax',)


class ProductSerializer(ProductPaymentInfoMixin, serializers.HyperlinkedModelSerializer):
    """ Serializer for Products. """
    attribute_values = serializers.SerializerMethodField()
    product_class = serializers.SerializerMethodField()
    is_available_to_buy = serializers.SerializerMethodField()
    is_enrollment_code_product = serializers.SerializerMethodField()
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

    def get_is_enrollment_code_product(self, product):
        return product.is_enrollment_code_product

    class Meta:
        model = Product
        fields = (
            'id', 'url', 'structure', 'product_class', 'title', 'price', 'expires', 'attribute_values',
            'is_available_to_buy', 'is_enrollment_code_product', 'stockrecords'
        )
        extra_kwargs = {
            'url': {'view_name': PRODUCT_DETAIL_VIEW},
        }


class LineSerializer(serializers.ModelSerializer):
    """Serializer for parsing line item data."""
    product = ProductSerializer()
    course_organization = serializers.SerializerMethodField()

    def get_course_organization(self, line):
        try:
            if line.product.course:
                return CourseKey.from_string(line.product.course.id).org
        except (AttributeError, TypeError, ValueError):
            logger.exception(
                '[Receipt MFE] Failed to retrieve course organization for line [%s]',
                line
            )
        return None

    class Meta:
        model = Line
        fields = (
            'title', 'quantity', 'course_organization', 'description', 'status', 'line_price_excl_tax',
            'unit_price_excl_tax', 'product'
        )


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for parsing order data."""
    basket_discounts = serializers.SerializerMethodField()
    billing_address = BillingAddressSerializer(allow_null=True)
    contains_credit_seat = serializers.SerializerMethodField()
    dashboard_url = serializers.SerializerMethodField()
    date_placed = serializers.DateTimeField(format=ISO_8601_FORMAT)
    discount = serializers.SerializerMethodField()
    lines = LineSerializer(many=True)
    payment_processor = serializers.SerializerMethodField()
    product_tracking = serializers.SerializerMethodField()
    user = UserSerializer()
    vouchers = serializers.SerializerMethodField()
    enable_hoist_order_history = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    enterprise_learner_portal_url = serializers.SerializerMethodField()
    total_before_discounts_incl_tax = serializers.SerializerMethodField()
    order_product_ids = serializers.SerializerMethodField()

    def get_basket_discounts(self, obj):
        basket_discounts = []
        try:
            discounts = obj.basket_discounts
            if discounts:
                for discount in discounts:
                    basket_discount = {
                        'amount': discount.amount,
                        'benefit_value': discount.voucher.benefit.value if discount.voucher else None,
                        'code': discount.voucher_code,
                        'condition_name': discount.offer.condition.name if discount.offer else None,
                        'contains_offer': bool(discount.offer),
                        'currency': obj.currency,
                        'enterprise_customer_name':
                            discount.offer.condition.enterprise_customer_name if discount.offer else None,
                        'offer_type': discount.offer.offer_type if discount.offer else None,
                    }
                    basket_discounts.append(basket_discount)
        except (AttributeError, TypeError, ValueError):
            logger.exception(
                '[Receipt MFE] Failed to retrieve basket discounts for [%s]',
                obj
            )
        return basket_discounts

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

    def get_dashboard_url(self, obj):
        try:
            return ReceiptResponseView.get_order_dashboard_url(self, obj)
        except ValueError:
            logger.exception(
                '[Receipt MFE] Failed to retrieve dashboard URL for [%s]',
                obj
            )
            return None

    def get_discount(self, obj):
        try:
            discount = obj.discounts.all()[0]
            return str(discount.amount)
        except IndexError:
            return '0'

    def get_contains_credit_seat(self, obj):
        try:
            return ReceiptResponseView().order_contains_credit_seat(obj)
        except ValueError:
            logger.exception(
                '[Receipt MFE] Failed to retrieve credit seat value for [%s]',
                obj
            )
            return None

    def get_enable_hoist_order_history(self, obj):
        try:
            request = self.context.get('request')
            return waffle.flag_is_active(request, ENABLE_HOIST_ORDER_HISTORY)
        except ValueError:
            logger.exception(
                'An error occurred while attempting to get ENABLE_HOIST_ORDER_HISTORY flag for order [%s]',
                obj
            )
            return None

    def get_payment_method(self, obj):
        payment_method = None
        try:
            payment_method = ReceiptResponseView().get_payment_method(obj)
        except ValueError:
            logger.exception(
                '[Receipt MFE] Failed to retrieve payment method for order [%s]',
                obj
            )
        return payment_method

    def get_enterprise_learner_portal_url(self, obj):
        try:
            request = self.context['request']
            enterprise_customer_user = ReceiptResponseView().get_metadata_for_enterprise_user(request)
            if not enterprise_customer_user:
                return None
            enterprise_customer = enterprise_customer_user['enterprise_customer']
            learner_portal_url = ReceiptResponseView().get_enterprise_learner_portal_url(
                request, enterprise_customer
            )
            return learner_portal_url
        except (AttributeError, ValueError):
            logger.exception(
                '[Receipt MFE] Failed to retrieve enterprise learner portal URL for order [%s]',
                obj
            )
            return None

    def get_total_before_discounts_incl_tax(self, obj):
        try:
            return str(obj.total_before_discounts_incl_tax)
        except ValueError:
            return None

    def get_order_product_ids(self, obj):
        try:
            return ','.join(map(str, obj.lines.values_list('product_id', flat=True)))
        except (AttributeError, ValueError):
            logger.exception(
                '[Receipt MFE] Failed to retrieve order product IDs for order [%s]',
                obj
            )
            return None

    def get_product_tracking(self, obj):
        try:
            if settings.AWIN_ADVERTISER_ID and obj.lines:
                return ReceiptResponseView.add_product_tracking(self, obj)
        except (AttributeError, ValueError):
            logger.exception(
                '[Receipt MFE] Failed to retrieve AWIN product tracking for order [%s]',
                obj
            )
        return None

    class Meta:
        model = Order
        fields = (
            'basket_discounts',
            'billing_address',
            'contains_credit_seat',
            'currency',
            'date_placed',
            'dashboard_url',
            'discount',
            'enable_hoist_order_history',
            'enterprise_learner_portal_url',
            'lines',
            'number',
            'order_product_ids',
            'payment_processor',
            'payment_method',
            'product_tracking',
            'status',
            'total_before_discounts_incl_tax',
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

    class Meta:
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

    class Meta:
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
        return bool(obj.enrollment_code_product)

    class Meta:
        model = Course
        fields = (
            'id', 'url', 'name', 'verification_deadline', 'type',
            'products_url', 'last_edited', 'products', 'has_active_bulk_enrollment_code')
        read_only_fields = ('type', 'products', 'site')
        extra_kwargs = {
            'url': {'view_name': COURSE_DETAIL_VIEW}
        }


class EntitlementProductHelper:
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

        # Extract arguments required for Entitlement creation, deserializing as necessary.
        certificate_type = attrs.get('certificate_type')
        price = Decimal(product['price'])

        # DISCO-1540 Temporarily force a default of id_verified=True for Professional entitlements
        id_verified_default = certificate_type == 'professional'
        id_verification_required = attrs.get('id_verification_required', id_verified_default)

        variant_id = attrs.get('variant_id')
        credit_provider = attrs.get('credit_provider')

        entitlement = create_or_update_course_entitlement(
            certificate_type,
            price,
            partner,
            uuid,
            course.name,
            id_verification_required=id_verification_required,
            credit_provider=credit_provider,
            variant_id=variant_id,
        )

        # As a convenience to our caller, provide the SKU in the returned product serialization.
        # We only create one stockrecord per product, so this first() business is safe.
        product['partner_sku'] = entitlement.stockrecords.first().partner_sku


class SeatProductHelper:
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
        sku = None
        stockrecords = product.get('stockrecords', [])
        if stockrecords:
            sku = stockrecords[0].get('partner_sku')

        seat = course.create_or_update_seat(
            certificate_type,
            id_verification_required,
            price,
            expires=expires,
            credit_provider=credit_provider,
            credit_hours=credit_hours,
            create_enrollment_code=create_enrollment_code,
            sku=sku,
        )

        # As a convenience to our caller, provide the SKU in the returned product serialization.
        # We only create one stockrecord per product, so this first() business is safe.
        product['partner_sku'] = seat.stockrecords.first().partner_sku


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

    def save(self):  # pylint: disable=arguments-differ
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
                raise Exception(resp_message)

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(u'Failed to save and publish [%s]: [%s]', course_id, str(e))
            return False, e, str(e)


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

    class Meta:
        model = Partner
        fields = ('id', 'name', 'short_code', 'catalogs', 'products')


class CatalogSerializer(serializers.ModelSerializer):
    """ Serializer for Catalogs. """
    products = serializers.SerializerMethodField()

    class Meta:
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
    type = serializers.SerializerMethodField()

    class Meta:
        model = Benefit
        fields = ('type', 'value')

    def get_type(self, benefit):
        return get_benefit_type(benefit)


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

    class Meta:
        model = Voucher
        fields = (
            'id', 'name', 'code', 'redeem_url', 'usage', 'start_datetime', 'end_datetime', 'num_basket_additions',
            'num_orders', 'total_discount', 'date_created', 'offers', 'is_available_to_user', 'benefit',
            'is_public',
        )


class CodeUsageSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    code = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    redeem_url = serializers.SerializerMethodField()
    redemptions = serializers.SerializerMethodField()
    assignment_date = serializers.SerializerMethodField()
    last_reminder_date = serializers.SerializerMethodField()
    revocation_date = serializers.SerializerMethodField()
    is_public = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        """
        Takes an optional `ignore_fields` argument that allows
        for the dynamic exclusion of fields during serialization.
        See: https://www.django-rest-framework.org/api-guide/serializers/#dynamically-modifying-fields
        """
        ignore_fields = kwargs.pop('ignore_fields', None)
        super().__init__(*args, **kwargs)

        if ignore_fields is not None:
            for field_name in ignore_fields:
                self.fields.pop(field_name, None)

    def _get_assignment(self, obj):
        assigned_to = self.get_assigned_to(obj)
        code = self.get_code(obj)
        if assigned_to and code:
            return OfferAssignment.objects.filter(code=code, user_email=assigned_to).first()
        return None

    def get_assignment_date(self, obj):
        assignment = self._get_assignment(obj)
        if assignment:
            return assignment.assignment_date.strftime("%B %d, %Y %H:%M") \
                if assignment.assignment_date else assignment.created.strftime("%B %d, %Y %H:%M")
        return ''

    def get_last_reminder_date(self, obj):
        last_reminder_date = getattr(self._get_assignment(obj), 'last_reminder_date', None)
        return last_reminder_date.strftime("%B %d, %Y %H:%M") if last_reminder_date else ''

    def get_revocation_date(self, obj):
        revocation_date = getattr(self._get_assignment(obj), 'revocation_date', None)
        return revocation_date.strftime("%B %d, %Y %H:%M") if revocation_date else ''

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

    def get_is_public(self, obj):
        voucher = Voucher.objects.get(code=self.get_code(obj))
        return voucher.is_public

    def num_assignments(self, code, user_email=None):
        offer_assignments = OfferAssignment.objects.filter(
            code=code,
            status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING, OFFER_ASSIGNMENT_EMAIL_BOUNCED],
        )
        if user_email:
            offer_assignments = offer_assignments.filter(user_email=user_email)

        return offer_assignments.count()


class NotAssignedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_assigned_to(self, obj):
        return ''

    def get_redemptions(self, obj):
        redemptions = super(NotAssignedCodeUsageSerializer, self).get_redemptions(obj)
        return dict(redemptions, num_assignments=self.num_assignments(code=self.get_code(obj)))


class NotRedeemedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_redemptions(self, obj):
        usage_type = self.context.get('usage_type')
        if usage_type in (Voucher.SINGLE_USE, Voucher.MULTI_USE_PER_CUSTOMER):
            return super(NotRedeemedCodeUsageSerializer, self).get_redemptions(obj)

        num_assignments = self.num_assignments(code=self.get_code(obj), user_email=self.get_assigned_to(obj))
        return {'used': 0, 'total': num_assignments}


class PartialRedeemedCodeUsageSerializer(CodeUsageSerializer):  # pylint: disable=abstract-method

    def get_redemptions(self, obj):
        usage_type = self.context.get('usage_type')
        if usage_type == Voucher.SINGLE_USE:
            return {}

        if usage_type == Voucher.MULTI_USE_PER_CUSTOMER:
            return super(PartialRedeemedCodeUsageSerializer, self).get_redemptions(obj)

        num_assignments = self.num_assignments(code=self.get_code(obj), user_email=self.get_assigned_to(obj))
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

    class Meta:
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
        return None

    class Meta:
        model = Product
        fields = ('category', 'client', 'code', 'id', 'title', 'date_created')


def _serialize_remaining_balance_value(conditional_offer):
    """
    Calculate and return remaining balance on the offer.
    """
    remaining_balance = calculate_remaining_offer_balance(conditional_offer)
    if remaining_balance is not None:
        remaining_balance = str(remaining_balance)
    return remaining_balance


def _serialize_remaining_balance_for_user(conditional_offer, request):
    """
    Determines the remaining balance for the user.
    """
    if request and conditional_offer.max_user_discount is not None:
        return str(conditional_offer.max_user_discount - sum_user_discounts_for_offer(request.user, conditional_offer))
    return None


def _serialize_remaining_applications_value(conditional_offer):
    """
    Calculate and return remaining number of applications on the offer.
    """
    if conditional_offer.max_global_applications is not None:
        return conditional_offer.max_global_applications - conditional_offer.num_applications
    return None


def _serialize_remaining_applications_for_user(conditional_offer, request):
    """
    Determines the remaining number of applications (enrollments) for the user.
    """
    if request and conditional_offer.max_user_applications is not None:
        return conditional_offer.max_user_applications - conditional_offer.get_num_user_applications(request.user)
    return None


class EnterpriseLearnerOfferApiSerializer(serializers.BaseSerializer):  # pylint: disable=abstract-method
    """
    Serializer for EnterpriseOffer learner endpoint.

    Uses serializers.BaseSerializer to keep this lightweight.
    """

    def to_representation(self, instance):
        representation = OrderedDict()

        representation['id'] = instance.id
        representation['enterprise_customer_uuid'] = instance.condition.enterprise_customer_uuid
        representation['enterprise_catalog_uuid'] = instance.condition.enterprise_customer_catalog_uuid
        representation['is_current'] = instance.is_current
        representation['status'] = instance.status
        representation['start_datetime'] = instance.start_datetime
        representation['end_datetime'] = instance.end_datetime
        representation['usage_type'] = get_benefit_type(instance.benefit)
        representation['discount_value'] = instance.benefit.value
        representation['max_discount'] = instance.max_discount
        representation['max_global_applications'] = instance.max_global_applications
        representation['max_user_applications'] = instance.max_user_applications
        representation['max_user_discount'] = instance.max_user_discount
        representation['num_applications'] = instance.num_applications
        representation['remaining_balance'] = _serialize_remaining_balance_value(instance)
        representation['remaining_applications'] = _serialize_remaining_applications_value(instance)
        representation['remaining_balance_for_user'] = \
            _serialize_remaining_balance_for_user(instance, request=self.context.get('request'))
        representation['remaining_applications_for_user'] = \
            _serialize_remaining_applications_for_user(instance, request=self.context.get('request'))

        return representation


class EnterpriseAdminOfferApiSerializer(serializers.ModelSerializer):  # pylint: disable=abstract-method
    """
    Serializer for EnterpriseOffer admin endpoint.

    Uses serializers.ModelSerializer to get __all__ fields serialized easily.
    Opted not to use inheritance from EnterpriseLearnerOfferApiSerializer
    due to complexity around overriding serializer's Meta class.
    """

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        representation['usage_type'] = get_benefit_type(instance.benefit)
        representation['discount_value'] = instance.benefit.value
        representation['enterprise_customer_uuid'] = instance.condition.enterprise_customer_uuid
        representation['enterprise_catalog_uuid'] = instance.condition.enterprise_customer_catalog_uuid
        representation['display_name'] = generate_offer_display_name(instance)
        representation['remaining_balance'] = _serialize_remaining_balance_value(instance)
        representation['remaining_applications'] = _serialize_remaining_applications_value(instance)
        representation['is_current'] = instance.is_current

        return representation

    class Meta:
        model = ConditionalOffer
        fields = '__all__'


class OfferAssignmentSummarySerializer(serializers.BaseSerializer):  # pylint: disable=abstract-method
    """
    Serializer for OfferAssignment endpoint.
    """

    def to_representation(self, instance):
        representation = OrderedDict()

        offer_assignment = instance['obj']
        representation['usage_type'] = get_benefit_type(offer_assignment.offer.benefit)
        representation['benefit_value'] = offer_assignment.offer.benefit.value

        representation['redemptions_remaining'] = instance['count']
        representation['code'] = offer_assignment.code
        representation['catalog'] = offer_assignment.offer.condition.enterprise_customer_catalog_uuid
        representation['coupon_start_date'] = offer_assignment.offer.vouchers.first().start_datetime
        representation['coupon_end_date'] = offer_assignment.offer.vouchers.first().end_datetime

        return representation


class TemplateFileAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateFileAttachment
        fields = "__all__"


class OfferAssignmentEmailTemplatesSerializer(serializers.ModelSerializer):
    enterprise_customer = serializers.UUIDField(read_only=True)
    email_body = serializers.SerializerMethodField()
    email_files = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OfferAssignmentEmailTemplates
        fields = '__all__'

    def validate_email_greeting(self, value):
        if len(value) > OFFER_ASSIGNMENT_EMAIL_TEMPLATE_FIELD_LIMIT:
            raise serializers.ValidationError(
                'Email greeting must be {} characters or less'.format(OFFER_ASSIGNMENT_EMAIL_TEMPLATE_FIELD_LIMIT)
            )
        return value

    def validate_email_closing(self, value):
        if len(value) > OFFER_ASSIGNMENT_EMAIL_TEMPLATE_FIELD_LIMIT:
            raise serializers.ValidationError(
                'Email closing must be {} characters or less'.format(OFFER_ASSIGNMENT_EMAIL_TEMPLATE_FIELD_LIMIT)
            )
        return value

    def validate_email_subject(self, value):
        if len(value) > OFFER_ASSIGNMENT_EMAIL_SUBJECT_LIMIT:
            raise serializers.ValidationError(
                'Email subject must be {} characters or less'.format(OFFER_ASSIGNMENT_EMAIL_SUBJECT_LIMIT)
            )
        return value

    def create(self, validated_data):
        enterprise_customer = self.context['view'].kwargs.get('enterprise_customer')
        email_type = validated_data['email_type']
        email_greeting = bleach.clean(validated_data.get('email_greeting', ''))
        email_closing = bleach.clean(validated_data.get('email_closing', ''))
        email_subject = bleach.clean(validated_data.get('email_subject', ''))

        create_data = dict(
            enterprise_customer=enterprise_customer,
            email_type=email_type,
            email_greeting=email_greeting,
            email_closing=email_closing,
            email_subject=email_subject,
        )

        if 'name' in validated_data:
            create_data['name'] = validated_data.get('name')

        instance = OfferAssignmentEmailTemplates.objects.create(**create_data)

        # deactivate old templates for enterprise for this specific email type
        OfferAssignmentEmailTemplates.objects.filter(
            enterprise_customer=enterprise_customer,
            email_type=email_type,
        ).exclude(pk=instance.pk).update(active=False)

        return instance

    def get_email_body(self, obj):
        return settings.OFFER_ASSIGNMEN_EMAIL_TEMPLATE_BODY_MAP[obj.email_type]

    def get_email_files(self, obj):
        template = OfferAssignmentEmailTemplates.objects.get(id=obj.id)
        files = TemplateFileAttachment.objects.filter(template=template).all()
        files = TemplateFileAttachmentSerializer(files, many=True)
        return files.data


class EnterpriseCouponOverviewListSerializer(serializers.ModelSerializer):
    """
    Serializer for Enterprise Coupons list overview.
    """

    def _get_num_unassigned(self, vouchers):
        """
        Return number of available assignments.
        """
        all_slots_available = 0
        enterprise_offer = vouchers.first().enterprise_offer

        assignments = OfferAssignment.objects.filter(code__in=vouchers.values_list('code', flat=True)).exclude(
            status__in=[OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]
        ).values('code').annotate(num_assignments=Count('code')).order_by('code')

        vouchers_num_assignments = {item['code']: item['num_assignments'] for item in assignments}

        for voucher in vouchers:
            num_assignments = vouchers_num_assignments.get(voucher.code, 0)
            voucher_slots_available = voucher.calculate_available_slots(
                enterprise_offer.max_global_applications,
                num_assignments
            )
            if voucher_slots_available > 0:
                all_slots_available += voucher_slots_available

        return all_slots_available

    def _get_errors(self, coupon):
        """
        Returns a list of OfferAssignment errors associated with coupon.
        """
        codes = coupon.attr.coupon_vouchers.vouchers.values_list('code', flat=True)
        offer_assignments_with_error = OfferAssignment.objects.filter(
            code__in=codes,
            status=OFFER_ASSIGNMENT_EMAIL_BOUNCED
        )
        return OfferAssignmentSerializer(offer_assignments_with_error, many=True).data

    # Max number of codes available (Maximum Coupon Usage).
    def _get_max_uses(self, voucher, voucher_usage, voucher_count):
        offer = voucher.best_offer

        max_uses_per_code = None
        if voucher_usage == Voucher.SINGLE_USE:
            max_uses_per_code = 1
        elif offer.max_global_applications:
            max_uses_per_code = offer.max_global_applications
        else:
            max_uses_per_code = OFFER_MAX_USES_DEFAULT

        return max_uses_per_code * voucher_count

    def to_representation(self, coupon):  # pylint: disable=arguments-differ
        representation = super(EnterpriseCouponOverviewListSerializer, self).to_representation(coupon)

        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        voucher = vouchers.first()
        usage = voucher.usage
        count = vouchers.count()
        num_orders = vouchers.aggregate(Sum('num_orders'))

        data = {
            'start_date': voucher.start_datetime,
            'end_date': voucher.end_datetime,
            'num_uses': num_orders['num_orders__sum'],
            'usage_limitation': usage,
            'num_codes': count,
            'max_uses': self._get_max_uses(voucher, usage, count),
            'num_unassigned': self._get_num_unassigned(vouchers),
            'errors': self._get_errors(coupon),
            'available': is_coupon_available(coupon),
            'enterprise_catalog_uuid': retrieve_enterprise_customer_catalog(coupon),
        }

        return dict(representation, **data)

    class Meta:
        model = Product
        fields = ('id', 'title')


class EnterpriseCouponSearchSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for enterprise coupon search endpoint.
    """

    def to_representation(self, instance):
        """
        Return the data gathered by view for the serialized
        representation to hand back in response.
        """
        return instance


class EnterpriseCouponListSerializer(CouponMixin, serializers.ModelSerializer):
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

    class Meta:
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


class CouponSerializer(CouponMixin, ProductPaymentInfoMixin, serializers.ModelSerializer):
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
    enterprise_catalog_content_metadata_url = serializers.SerializerMethodField()
    enterprise_customer = serializers.SerializerMethodField()
    enterprise_customer_catalog = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    inactive = serializers.SerializerMethodField()
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
    contract_discount_value = serializers.SerializerMethodField()
    contract_discount_type = serializers.SerializerMethodField()
    prepaid_invoice_amount = serializers.SerializerMethodField()
    sales_force_id = serializers.SerializerMethodField()
    salesforce_opportunity_line_item = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'benefit_type', 'benefit_value', 'catalog_query', 'course_catalog', 'category',
            'client', 'code', 'code_status', 'coupon_type', 'course_seat_types', 'email_domains',
            'end_date', 'enterprise_catalog_content_metadata_url', 'enterprise_customer', 'enterprise_customer_catalog',
            'id', 'inactive', 'last_edited', 'max_uses', 'note', 'notify_email', 'num_uses', 'payment_information',
            'program_uuid', 'price', 'quantity', 'seats', 'start_date', 'title', 'voucher_type',
            'contract_discount_value', 'contract_discount_type', 'prepaid_invoice_amount',
            'sales_force_id', 'salesforce_opportunity_line_item',
        )

    def get_prepaid_invoice_amount(self, obj):
        try:
            return obj.attr.enterprise_contract_metadata.amount_paid
        except AttributeError:
            return None

    def get_contract_discount_value(self, obj):
        try:
            return obj.attr.enterprise_contract_metadata.discount_value
        except AttributeError:
            return None

    def get_contract_discount_type(self, obj):
        try:
            return obj.attr.enterprise_contract_metadata.discount_type
        except AttributeError:
            return None

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
        return None

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

    def get_enterprise_catalog_content_metadata_url(self, obj):
        uuid = self.get_enterprise_customer_catalog(obj)
        return urljoin(
            f"{settings.ENTERPRISE_CATALOG_API_URL}/",
            f"enterprise-catalogs/{str(uuid)}/get_content_metadata"
        ) if uuid else ''

    def get_enterprise_customer(self, obj):
        """ Get the Enterprise Customer attached to a coupon. """
        offer_range = retrieve_range(obj)
        offer_condition = retrieve_condition(obj)
        if offer_range and offer_range.enterprise_customer:
            return {
                'id': offer_range.enterprise_customer,
            }
        if offer_condition.enterprise_customer_uuid:
            return {
                'id': offer_condition.enterprise_customer_uuid,
                'name': offer_condition.enterprise_customer_name,
            }
        return None

    def get_enterprise_customer_catalog(self, obj):
        """ Get the Enterprise Customer Catalog UUID attached to a coupon. """
        return retrieve_enterprise_customer_catalog(obj)

    def get_inactive(self, obj):
        """ Get inactive attribute for Coupon Product"""
        try:
            return obj.attr.inactive
        except AttributeError:
            return False

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

    def get_sales_force_id(self, obj):
        """ Get the Sales Force Opportunity ID attached to the coupon. """
        try:
            return obj.attr.sales_force_id
        except AttributeError:
            return None

    def get_salesforce_opportunity_line_item(self, obj):
        """ Get the Salesforce Opportunity Line Item attached to the coupon. """
        try:
            return obj.attr.salesforce_opportunity_line_item
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

    def validate_sales_force_id_format(self):
        """
        Validate sales_force_id format
        """
        sales_force_id = self.initial_data.get('sales_force_id')
        if sales_force_id and not re.match(ENTERPRISE_SALES_FORCE_ID_REGEX, sales_force_id):
            raise ValidationError({
                'sales_force_id': 'Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006.'
            })

    def validate_salesforce_opportunity_line_item_format(self):
        """
        Validate salesforce_opportunity_line_item format
        """
        salesforce_opportunity_line_item = self.initial_data.get('salesforce_opportunity_line_item')
        if salesforce_opportunity_line_item and not\
                re.match(ENTERPRISE_SALESFORCE_OPPORTUNITY_LINE_ITEM_REGEX, salesforce_opportunity_line_item):
            raise ValidationError({
                'salesforce_opportunity_line_item':
                'Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number.'
            })


class CouponUpdateSerializer(CouponSerializer):
    """
    Serializer to update the Coupon.
    """
    def validate(self, attrs):
        """
        Validates the data.
        """
        validated_data = super(CouponUpdateSerializer, self).validate(attrs)
        # Validate max_uses
        max_uses = self.initial_data.get('max_uses')
        if max_uses is not None:
            if self.get_voucher_type(self.instance) == Voucher.SINGLE_USE:
                log_message_and_raise_validation_error(
                    'Failed to update Coupon. '
                    'max_global_applications field cannot be set for voucher type [{voucher_type}].'.format(
                        voucher_type=Voucher.SINGLE_USE
                    ))
            try:
                max_uses = int(max_uses)
                if max_uses < 1:
                    raise ValueError
            except ValueError as value_error:
                raise ValidationError('max_global_applications field must be a positive number.') from value_error

        return validated_data


class EnterpriseCouponCreateSerializer(CouponSerializer):
    """
    Serializer to create the Enterprise Coupon.
    """
    def validate(self, attrs):
        """
        Validates the data.
        """
        validated_data = super(EnterpriseCouponCreateSerializer, self).validate(attrs)

        # Validate salesforce_opportunity_line_item
        salesforce_opportunity_line_item = self.initial_data.get('salesforce_opportunity_line_item')
        if not salesforce_opportunity_line_item:
            raise ValidationError({
                'salesforce_opportunity_line_item': 'This field is required.'
            })
        self.validate_salesforce_opportunity_line_item_format()

        # Validate sales_force_id if it exists
        sales_force_id = self.initial_data.get('sales_force_id')
        if sales_force_id:
            self.validate_sales_force_id_format()

        return validated_data


class EnterpriseCouponUpdateSerializer(CouponUpdateSerializer):
    """
    Serializer to create the Enterprise Coupon.
    """
    def validate(self, attrs):
        """
        Validates the data.
        """
        validated_data = super(EnterpriseCouponUpdateSerializer, self).validate(attrs)

        # Validate salesforce_opportunity_line_item
        salesforce_opportunity_line_item = self.initial_data.get('salesforce_opportunity_line_item')
        if 'salesforce_opportunity_line_item' in self.initial_data and not salesforce_opportunity_line_item:
            raise ValidationError({
                'salesforce_opportunity_line_item': 'This field is required.'
            })
        self.validate_salesforce_opportunity_line_item_format()

        # Validate sales_force_id if it exists
        sales_force_id = self.initial_data.get('sales_force_id')
        if sales_force_id:
            self.validate_sales_force_id_format()
        return validated_data


class CheckoutSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    payment_form_data = serializers.SerializerMethodField()
    payment_page_url = serializers.URLField()
    payment_processor = serializers.CharField()

    def get_payment_form_data(self, obj):
        return obj['payment_form_data']


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
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
    class Meta:
        model = OfferAssignment
        fields = ('id', 'user_email', 'code')


class UserDetailSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    lms_user_id = serializers.CharField(required=False)
    email = serializers.CharField(required=True)
    username = serializers.CharField(required=False)


class CouponCodeAssignmentSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    codes = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    offer_assignments = serializers.ListField(
        child=OfferAssignmentSerializer(), read_only=True
    )
    users = serializers.ListField(
        child=UserDetailSerializer(), required=True, write_only=True,
    )
    base_enterprise_url = serializers.URLField(required=False, write_only=True)
    enable_nudge_emails = serializers.BooleanField(default=False)
    notify_learners = serializers.BooleanField(default=True)

    def create(self, validated_data):
        """
        Create OfferAssignment objects for each users_detail and the available_assignments determined from validation.
        """
        users = validated_data['users']
        voucher_usage_type = validated_data.pop('voucher_usage_type')
        subject = validated_data.pop('subject')
        greeting = validated_data.pop('greeting')
        closing = validated_data.pop('closing')
        files = self.context.get('files', [])
        sender_id = validated_data.pop('sender_id')
        template = validated_data.pop('template')
        enterprise_customer_uuid = validated_data.pop('enterprise_customer_uuid')
        enable_nudge_emails = validated_data.pop('enable_nudge_emails')
        available_assignments = validated_data.pop('available_assignments')
        users_iterator = iter(users)
        offer_assignments = []
        emails_already_sent = set()
        current_date_time = timezone.now()
        base_enterprise_url = validated_data.pop('base_enterprise_url', '')
        site = self.context.get('site')
        notify_learners = validated_data.pop('notify_learners', True)

        for code in available_assignments:
            offer = available_assignments[code]['offer']
            user = next(users_iterator) if voucher_usage_type == Voucher.MULTI_USE_PER_CUSTOMER else None
            for _ in range(available_assignments[code]['num_slots']):
                user_detail = user or next(users_iterator)
                new_offer_assignment = OfferAssignment.objects.create(
                    offer=offer,
                    code=code,
                    user_email=user_detail['email'],
                    assignment_date=current_date_time,
                )
                offer_assignments.append(new_offer_assignment)
                # Start async email task. For MULTI_USE_PER_CUSTOMER, a single email is sent
                email_code_pair = frozenset((new_offer_assignment.user_email, new_offer_assignment.code))
                if not notify_learners:
                    continue
                if email_code_pair not in emails_already_sent:
                    # subscribe the user for nudge email if enable_nudge_emails flag is on.
                    if enable_nudge_emails:
                        CodeAssignmentNudgeEmails.subscribe_nudge_emails(
                            user_email=user_detail['email'],
                            code=code,
                            base_enterprise_url=base_enterprise_url,
                        )
                    sender_alias = get_enterprise_customer_sender_alias(site, enterprise_customer_uuid)
                    reply_to = get_enterprise_customer_reply_to_email(site, enterprise_customer_uuid)
                    self._trigger_email_sending_task(
                        subject, greeting, closing, new_offer_assignment, voucher_usage_type, sender_alias,
                        reply_to, base_enterprise_url, attachments=files,
                    )
                    # Create a record of the email sent
                    create_offer_assignment_email_sent_record(
                        enterprise_customer_uuid,
                        ASSIGN,
                        template,
                        code=code,
                        user_email=user_detail['email'],
                        receiver_id=user_detail.get('lms_user_id'),
                        sender_id=sender_id
                    )
                    emails_already_sent.add(email_code_pair)
        validated_data['offer_assignments'] = offer_assignments
        return validated_data

    def validate(self, attrs):  # pylint: disable=too-many-statements
        """
        Validate that the given emails can be assigned to a slot in the coupon, to the codes if specified.
        A slot is a potential redemption of a voucher contained within the top level Coupon.
        """
        codes = attrs.get('codes')
        users = attrs['users']
        coupon = self.context.get('coupon')
        subject = self.context.get('subject')
        greeting = self.context.get('greeting')
        closing = self.context.get('closing')
        template_id = self.context.get('template_id', None)
        sender_id = self.context.get('sender_id', None)
        emails = [user['email'] for user in users]
        template = OfferAssignmentEmailTemplates.get_template(template_id)
        available_assignments = {}
        vouchers = coupon.attr.coupon_vouchers.vouchers
        try:
            enterprise_customer_uuid = coupon.attr.enterprise_customer_uuid
        except AttributeError:
            enterprise_customer_uuid = get_enterprise_customer_uuid_from_voucher(vouchers.first())

        # Limit which vouchers to consider for assignment by the codes passed in.
        if codes:
            vouchers = vouchers.filter(code__in=codes)

        # For ONCE_PER_CUSTOMER Coupons, exclude vouchers that have already
        # been assigned to or redeemed by the requested emails.
        voucher_usage_type = vouchers.first().usage
        if voucher_usage_type == Voucher.ONCE_PER_CUSTOMER:
            existing_assignments_for_users = OfferAssignment.objects.filter(user_email__in=emails).exclude(
                status__in=[OFFER_ASSIGNMENT_REVOKED]
            )
            existing_applications_for_users = VoucherApplication.objects.select_related('user').filter(
                user__email__in=emails
            )
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
                'codes: %s, emails: %s, coupon_id: %s',
                set(codes_to_exclude), set(emails_requiring_exclusions), coupon.id
            )
            vouchers = vouchers.exclude(code__in=codes_to_exclude)

        vouchers = vouchers.all()
        prefetch_related_objects(vouchers, 'offers', 'offers__condition', 'offers__offerassignment_set')
        total_slots = 0
        for voucher in vouchers:
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
        attrs['voucher_usage_type'] = voucher_usage_type
        attrs['available_assignments'] = available_assignments
        attrs['subject'] = subject
        attrs['greeting'] = greeting
        attrs['closing'] = closing
        attrs['sender_id'] = sender_id
        attrs['template'] = template
        attrs['enterprise_customer_uuid'] = enterprise_customer_uuid
        return attrs

    def _trigger_email_sending_task(self, subject, greeting, closing, assigned_offer, voucher_usage_type, sender_alias,
                                    reply_to, base_enterprise_url='', attachments=None):
        """
        Schedule async task to send email to the learner who has been assigned the code.
        """
        coupon = self.context.get('coupon')
        code_expiration_date = retrieve_end_date(coupon)
        redemptions_remaining = (
            assigned_offer.offer.max_global_applications if voucher_usage_type == Voucher.MULTI_USE_PER_CUSTOMER else 1
        )
        try:
            send_assigned_offer_email(
                subject=subject,
                greeting=greeting,
                closing=closing,
                offer_assignment_id=assigned_offer.id,
                learner_email=assigned_offer.user_email,
                code=assigned_offer.code,
                redemptions_remaining=redemptions_remaining,
                code_expiration_date=code_expiration_date.strftime('%d %B, %Y %H:%M %Z'),
                sender_alias=sender_alias,
                reply_to=reply_to,
                base_enterprise_url=base_enterprise_url,
                attachments=attachments,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(  # pylint: disable=logging-too-many-args
                '[Offer Assignment] Email for offer_assignment_id: %d with subject %r, '
                'greeting %r closing %r and attachments %r, raised exception: %r',
                assigned_offer.id,
                subject,
                greeting,
                closing,
                attachments,
                exc
            )


class RefundedOrderCreateVoucherSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
        Creates and assigns new coupon voucher to the user associated with the order.
    """
    order = serializers.CharField(required=True)
    code = serializers.CharField(read_only=True)

    def validate_order(self, order):
        """Verify the order number and return the order object."""
        try:
            order = Order.objects.get(number=order)
        except Order.DoesNotExist as order_no_exist:
            # pylint: disable=line-too-long
            raise serializers.ValidationError(_('Invalid order number or order {} does not exists.').format(order)) from order_no_exist
        return order

    def create(self, validated_data):
        """Create new voucher in existing coupon and assign it to the given user_emails"""
        coupon_product = validated_data.get('coupon_product')
        benefit_type = validated_data.get('benefit_type')
        benefit_value = validated_data.get('benefit_value')
        enterprise_customer_uuid = validated_data.get('enterprise_customer_uuid')
        enterprise_customer_catalog_uuid = validated_data.get('enterprise_customer_catalog_uuid')
        email_domains = validated_data.get('email_domains')
        start_datetime = validated_data.get('start_datetime')
        end_datetime = validated_data.get('end_datetime')
        site = validated_data.get('site')
        note = validated_data.get('note')
        users = validated_data.get('users')

        vouchers = create_enterprise_vouchers(
            voucher_type=Voucher.SINGLE_USE,
            quantity=1,
            coupon_id=coupon_product.id,
            benefit_type=benefit_type,
            benefit_value=benefit_value,
            enterprise_customer=enterprise_customer_uuid,
            enterprise_customer_catalog=enterprise_customer_catalog_uuid,
            max_uses=None,
            email_domains=email_domains,
            site=site,
            end_datetime=end_datetime,
            start_datetime=start_datetime,
            code=None,
            name=coupon_product.title
        )

        attach_vouchers_to_coupon_product(
            coupon_product,
            vouchers,
            note,
        )

        new_code = vouchers[0].code
        serializer = CouponCodeAssignmentSerializer(
            data={'codes': [new_code], 'users': users},
            context={
                'coupon': coupon_product,
                'subject': REFUND_ORDER_EMAIL_SUBJECT,
                'greeting': REFUND_ORDER_EMAIL_GREETING,
                'closing': REFUND_ORDER_EMAIL_CLOSING,
                'site': site,
            }
        )
        if serializer.is_valid():
            serializer.save()
        else:
            raise serializers.ValidationError(
                _("New coupon voucher assignment Failure. Error: {}").format(serializer.errors)
            )

        validated_data['code'] = new_code
        return validated_data

    def validate(self, attrs):
        """
        Extract and validates all data required data.
        """
        order = attrs.get('order')

        try:
            discount = order.discounts.first()
            offer = discount.offer
            existing_voucher = offer.vouchers.first()
            if not existing_voucher.usage == Voucher.SINGLE_USE:
                raise serializers.ValidationError(
                    _("Your order {} can not be refunded as '{}' coupon are not supported to refund.".format(
                        order, existing_voucher.usage
                    ))
                )
            benefit = offer.benefit
            condition = offer.condition
            coupon_product = existing_voucher.coupon_vouchers.first().coupon
            benefit_type = next(k for k, v in ENTERPRISE_BENEFIT_MAP.items() if class_path(v) == benefit.proxy_class)
            try:
                note = coupon_product.attr.note
            except AttributeError:
                note = None

            attrs['coupon_product'] = coupon_product
            attrs['benefit_type'] = benefit_type
            attrs['benefit_value'] = benefit.value
            attrs['enterprise_customer_uuid'] = condition.enterprise_customer_uuid
            attrs['enterprise_customer_catalog_uuid'] = condition.enterprise_customer_catalog_uuid
            attrs['email_domains'] = offer.email_domains
            attrs['start_datetime'] = existing_voucher.start_datetime
            attrs['end_datetime'] = existing_voucher.end_datetime
            attrs['site'] = self.context['request'].site
            attrs['users'] = [
                {
                    'email': order.user.email,
                    'username': order.user.username,
                    'lms_user_id': order.user.lms_user_id
                }
            ]
            attrs['note'] = note
        except AttributeError as attribute_error:
            error_message = _("Could note create new voucher for the order: {}").format(order)
            logger.exception(error_message)
            raise serializers.ValidationError(error_message) from attribute_error
        return attrs


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
                            'user': item.get('user'),
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


class CouponCodeMixin:

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
            status__in=[OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_PENDING, OFFER_ASSIGNMENT_EMAIL_BOUNCED]
        )


class CouponCodeRevokeSerializer(CouponCodeMixin, serializers.Serializer):  # pylint: disable=abstract-method

    class Meta:
        list_serializer_class = CouponCodeRevokeRemindBulkSerializer

    code = serializers.CharField(required=True)
    user = UserDetailSerializer(required=True)
    detail = serializers.CharField(read_only=True)
    do_not_email = serializers.BooleanField(default=False)

    def create(self, validated_data):
        """
        Update OfferAssignments to have Revoked status.
        """
        offer_assignments = validated_data.get('offer_assignments')
        user = validated_data.get('user')
        code = validated_data.get('code')

        # `not` is used here to avoid double negative in the if condition in the code ahead.
        # `should_send_revoke_email` shows whether a new email will be sent or not.
        should_send_revoke_email = not validated_data.get('do_not_email')

        sender_id = validated_data.pop('sender_id')
        template = validated_data.pop('template')
        enterprise_customer_uuid = validated_data.pop('enterprise_customer_uuid')
        subject = self.context.get('subject')
        greeting = self.context.get('greeting')
        closing = self.context.get('closing')
        base_enterprise_url = self.context.get('base_enterprise_url', '')
        files = self.context.get('files', [])
        site = self.context.get('site')
        detail = 'success'
        current_date_time = timezone.now()

        try:
            for offer_assignment in offer_assignments:
                offer_assignment.status = OFFER_ASSIGNMENT_REVOKED
                offer_assignment.revocation_date = current_date_time
                offer_assignment.save()

            if should_send_revoke_email:
                sender_alias = get_enterprise_customer_sender_alias(site, enterprise_customer_uuid)
                reply_to = get_enterprise_customer_reply_to_email(site, enterprise_customer_uuid)
                send_revoked_offer_email(
                    subject=subject,
                    greeting=greeting,
                    closing=closing,
                    learner_email=user['email'],
                    code=code,
                    sender_alias=sender_alias,
                    reply_to=reply_to,
                    base_enterprise_url=base_enterprise_url,
                    attachments=files,
                )
                # Create a record of the email sent
                create_offer_assignment_email_sent_record(
                    enterprise_customer_uuid,
                    REVOKE,
                    template,
                    code=code,
                    user_email=user['email'],
                    receiver_id=user.get('lms_user_id'),
                    sender_id=sender_id
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                '[Offer Revocation] Encountered error when revoking code %s for user %s with '
                'subject %r, greeting %r closing %r base_enterprise_url %r and files %r',
                code, user['email'], subject, greeting, closing, base_enterprise_url, files
            )
            detail = str(exc)

        validated_data['detail'] = detail
        return validated_data

    def validate(self, attrs):
        """
        Validate that the code is part of the Coupon and the provided code and email have an active OfferAssignment.
        """
        code = attrs.get('code')
        user = attrs.get('user')
        coupon = self.context.get('coupon')
        template_id = self.context.get('template_id', None)
        sender_id = self.context.get('sender_id', None)
        template = OfferAssignmentEmailTemplates.get_template(template_id)
        enterprise_customer_uuid = coupon.attr.enterprise_customer_uuid
        self.validate_coupon_has_code(coupon, code)
        offer_assignments = self.get_unredeemed_offer_assignments(code, user['email'])
        if not offer_assignments.exists():
            raise serializers.ValidationError(f'No assignments exist for user {user["email"]} and code {code}')
        attrs['offer_assignments'] = offer_assignments
        attrs['sender_id'] = sender_id
        attrs['template'] = template
        attrs['enterprise_customer_uuid'] = enterprise_customer_uuid
        return attrs


class CouponCodeRemindSerializer(CouponCodeMixin, serializers.Serializer):  # pylint: disable=abstract-method

    class Meta:
        list_serializer_class = CouponCodeRevokeRemindBulkSerializer

    code = serializers.CharField(required=True)
    user = UserDetailSerializer(required=True)
    detail = serializers.CharField(read_only=True)

    def create(self, validated_data):
        """
        Send remind email(s) for pending OfferAssignments.
        """

        offer_assignments = validated_data.get('offer_assignments')
        user = validated_data['user']
        code = validated_data.get('code')
        redeemed_offer_count = validated_data.get('redeemed_offer_count')
        total_offer_count = validated_data.get('total_offer_count')
        sender_id = validated_data.pop('sender_id')
        template = validated_data.pop('template')
        enterprise_customer_uuid = validated_data.pop('enterprise_customer_uuid')
        subject = self.context.get('subject')
        greeting = self.context.get('greeting')
        closing = self.context.get('closing')
        files = self.context.get('files', [])
        base_enterprise_url = self.context.get('base_enterprise_url', '')
        detail = 'success'
        current_date_time = timezone.now()
        site = self.context.get('site')

        sender_alias = get_enterprise_customer_sender_alias(site, enterprise_customer_uuid)
        reply_to = get_enterprise_customer_reply_to_email(site, enterprise_customer_uuid)
        try:
            self._trigger_email_sending_task(
                subject,
                greeting,
                closing,
                offer_assignments.first(),
                redeemed_offer_count,
                total_offer_count,
                sender_alias,
                reply_to,
                base_enterprise_url,
                attachments=files,
            )
            # Create a record of the email sent
            create_offer_assignment_email_sent_record(
                enterprise_customer_uuid,
                REMIND,
                template,
                code=code,
                user_email=user['email'],
                receiver_id=user.get('lms_user_id'),
                sender_id=sender_id,
            )
            for offer_assignment in offer_assignments:
                offer_assignment.last_reminder_date = current_date_time
                offer_assignment.save()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception('Encountered error during reminder email for code %s of user %s', code, user['email'])
            detail = str(exc)

        validated_data['detail'] = detail
        return validated_data

    def validate(self, attrs):
        """
        Validate that the code is part of the Coupon the code and email provided have an active OfferAssignment.
        """
        code = attrs.get('code')
        user = attrs.get('user')
        coupon = self.context.get('coupon')
        template_id = self.context.get('template_id', None)
        sender_id = self.context.get('sender_id', None)
        template = OfferAssignmentEmailTemplates.get_template(template_id)
        enterprise_customer_uuid = coupon.attr.enterprise_customer_uuid
        self.validate_coupon_has_code(coupon, code)
        offer_assignments = self.get_unredeemed_offer_assignments(code, user['email'])
        offer_assignments_redeemed = OfferAssignment.objects.filter(
            code=code,
            user_email=user['email'],
            status=OFFER_REDEEMED
        )
        if not offer_assignments.exists():
            raise serializers.ValidationError(f'No assignments exist for user {user["email"]} and code {code}')
        attrs['offer_assignments'] = offer_assignments
        attrs['redeemed_offer_count'] = offer_assignments_redeemed.count()
        attrs['total_offer_count'] = offer_assignments.count()
        attrs['sender_id'] = sender_id
        attrs['template'] = template
        attrs['enterprise_customer_uuid'] = enterprise_customer_uuid
        return attrs

    def _trigger_email_sending_task(
            self, subject, greeting, closing, assigned_offer, redeemed_offer_count, total_offer_count, sender_alias,
            reply_to, base_enterprise_url='', attachments=None,
    ):
        """
        Schedule async task to send email to the learner who has been assigned the code.
        """
        coupon = self.context.get('coupon')
        code_expiration_date = retrieve_end_date(coupon)
        try:
            send_assigned_offer_reminder_email(
                subject=subject,
                greeting=greeting,
                closing=closing,
                learner_email=assigned_offer.user_email,
                code=assigned_offer.code,
                redeemed_offer_count=redeemed_offer_count,
                total_offer_count=total_offer_count,
                code_expiration_date=code_expiration_date.strftime('%d %B, %Y %H:%M %Z'),
                sender_alias=sender_alias,
                reply_to=reply_to,
                attachments=attachments,
                base_enterprise_url=base_enterprise_url,
            )
        except Exception as exc:  # pylint: disable=broad-except
            # Log the exception here to help diagnose any template issues, then raise it for backwards compatibility
            logger.exception(  # pylint: disable=logging-too-many-args
                '[Offer Reminder] Email for offer_assignment_id: %d with subject %r, '
                'greeting %r closing %r attachments %r, and base_enterprise_url %r raised exception: %r',
                assigned_offer.id,
                subject,
                greeting,
                closing,
                attachments,
                base_enterprise_url,
                exc
            )
            raise

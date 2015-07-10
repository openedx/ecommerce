"""Serializers for order and line item data."""

from oscar.core.loading import get_model, get_class
from rest_framework import serializers
from rest_framework.reverse import reverse

from ecommerce.courses.models import Course
from ecommerce.extensions.payment.constants import ISO_8601_FORMAT

BillingAddress = get_model('order', 'BillingAddress')
Line = get_model('order', 'Line')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')
Refund = get_model('refund', 'Refund')
Selector = get_class('partner.strategy', 'Selector')

COURSE_DETAIL_VIEW = 'api:v2:course-detail'
PRODUCT_DETAIL_VIEW = 'api:v2:product-detail'


class BillingAddressSerializer(serializers.ModelSerializer):
    """Serializes a Billing Address. """
    city = serializers.CharField(max_length=255, source='line4')

    class Meta(object):
        model = BillingAddress
        fields = ('first_name', 'last_name', 'line1', 'line2', 'postcode', 'state', 'country', 'city')


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    """ Serializer for ProductAttributeValue objects. """
    name = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    def get_name(self, instance):
        return instance.attribute.name

    def get_value(self, obj):
        return obj.value

    class Meta(object):
        model = ProductAttributeValue
        fields = ('name', 'value',)


class ProductSerializer(serializers.HyperlinkedModelSerializer):
    """ Serializer for Products. """
    attribute_values = ProductAttributeValueSerializer(many=True, read_only=True)
    product_class = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    is_available_to_buy = serializers.SerializerMethodField()

    def get_product_class(self, product):
        return product.get_product_class().name

    def get_price(self, product):
        info = self._get_info(product)
        if info.availability.is_available_to_buy:
            return serializers.DecimalField(max_digits=10, decimal_places=2).to_representation(info.price.excl_tax)
        return None

    def _get_info(self, product):
        info = Selector().strategy().fetch_for_product(product)
        return info

    def get_is_available_to_buy(self, product):
        info = self._get_info(product)
        return info.availability.is_available_to_buy

    class Meta(object):
        model = Product
        fields = ('id', 'url', 'product_class', 'title', 'price', 'expires', 'attribute_values', 'is_available_to_buy',)
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

    class Meta(object):
        model = Order
        fields = ('number', 'date_placed', 'status', 'currency', 'total_excl_tax', 'lines', 'billing_address')


class PaymentProcessorSerializer(serializers.Serializer):   # pylint: disable=abstract-method
    """ Serializer to use with instances of processors.BasePaymentProcessor """

    def to_representation(self, instance):
        """ Serialize instances as a string instead of a mapping object. """
        return instance.NAME


class RefundSerializer(serializers.ModelSerializer):
    """ Serializer for Refund objects. """

    class Meta(object):
        model = Refund


class CourseSerializer(serializers.HyperlinkedModelSerializer):
    products_url = serializers.SerializerMethodField()

    def get_products_url(self, obj):
        return reverse('api:v2:course-product-list', kwargs={'parent_lookup_course_id': obj.id},
                       request=self.context['request'])

    class Meta(object):
        model = Course
        fields = ('id', 'url', 'name', 'products_url',)
        extra_kwargs = {
            'url': {'view_name': COURSE_DETAIL_VIEW}
        }

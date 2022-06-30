

from datetime import datetime

import django_filters
import pytz
from django.db.models import Q
from oscar.core.loading import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')


class ProductFilter(django_filters.FilterSet):
    """ Filter products via query string parameters. """
    product_class = django_filters.CharFilter(method='filter_product_class')
    structure = django_filters.CharFilter(field_name='structure', lookup_expr='iexact')

    def filter_product_class(self, queryset, name, value):  # pylint: disable=unused-argument
        return queryset.filter(Q(product_class__name__iexact=value) | Q(parent__product_class__name__iexact=value))

    class Meta:
        model = Product
        fields = ('product_class', 'structure',)


class OrderFilter(django_filters.FilterSet):
    """ Filter orders via query string parameter."""

    username = django_filters.CharFilter(field_name='user__username')

    class Meta:
        model = Order
        fields = ('username',)


class OfferApiFilter(django_filters.FilterSet):
    usage_type = django_filters.CharFilter(method='filter_by_usage_type')
    discount_value = django_filters.NumberFilter(field_name='benefit__value')
    is_current = django_filters.BooleanFilter(method='filter_is_current')

    def filter_is_current(self, queryset, name, value):  # pylint: disable=unused-argument
        now = datetime.now(pytz.UTC)

        query = Q(
            Q(start_datetime=None, end_datetime=None) |
            Q(start_datetime__lte=now, end_datetime=None) |
            Q(start_datetime=None, end_datetime__gte=now) |
            Q(start_datetime__lte=now, end_datetime__gte=now)
        )

        return queryset.filter(
            query if value else ~query
        )

    def filter_by_usage_type(self, queryset, name, value):  # pylint: disable=unused-argument

        usage_type_values = value.strip().lower().split(',')
        # proxy() is a method on the benefit that maps our class to the pretty Percentage name
        # but because it is an property so we cannot query the DB directly for it.
        # Do our own map here so API callers can just ask for percentage or absolute
        proxy_class_map = {
            'percentage': 'ecommerce.enterprise.benefits.EnterprisePercentageDiscountBenefit',
            'absolute': 'ecommerce.enterprise.benefits.EnterpriseAbsoluteDiscountBenefit',
        }
        usage_type_values = [
            proxy_class_map[value]
            for value in usage_type_values
            if value in proxy_class_map
        ]

        queryset = queryset.filter(benefit__proxy_class__in=usage_type_values).distinct()
        return queryset

    class Meta:
        model = ConditionalOffer

        fields = {
            'status': ['exact'],
            'max_user_applications': ['isnull'],
            'max_user_discount': ['isnull']
        }

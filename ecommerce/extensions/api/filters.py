

import django_filters
from django.db.models import Q
from oscar.core.loading import get_model

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

import django_filters
from django.db.models import Q

from oscar.core.loading import get_model
from ecommerce.core.models import BusinessClient

Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')


class ProductFilter(django_filters.FilterSet):
    """ Filter products via query string parameters. """
    product_class = django_filters.MethodFilter()
    structure = django_filters.CharFilter(name='structure', lookup_type='iexact')
    title = django_filters.CharFilter(name='title', lookup_type='startswith')

    def filter_product_class(self, queryset, value):
        return queryset.filter(Q(product_class__name__iexact=value) | Q(parent__product_class__name__iexact=value))

    class Meta(object):
        model = Product
        fields = ('product_class', 'structure', 'title',)


class OrderFilter(django_filters.FilterSet):
    """ Filter orders via query string parameter."""

    username = django_filters.CharFilter(name='user__username')

    class Meta(object):
        model = Order
        fields = ('username',)


class ClientFilter(django_filters.FilterSet):
    """ Filter clients via query string parameter. """
    name = django_filters.CharFilter(name='name', lookup_type='iexact')

    class Meta(object):
        model = BusinessClient
        fields = ('name',)

import django_filters

from oscar.core.loading import get_model

Product = get_model('catalogue', 'Product')


class ProductFilter(django_filters.FilterSet):
    """ Filter products via query string parameters. """
    title = django_filters.CharFilter(name='title', lookup_type='startswith')

    class Meta(object):
        model = Product
        fields = ('title', )

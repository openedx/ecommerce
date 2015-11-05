from django.contrib.sites.models import Site
from django.utils import timezone
from oscar.apps.partner import availability, strategy
from oscar.core.loading import get_model


class CourseSeatAvailabilityPolicyMixin(strategy.StockRequired):
    """
    Availability policy for Course seats.

    Child seats are only available if the current date is not beyond the seat's enrollment close date.
    Parent seats are never available.
    """

    @property
    def seat_class(self):
        ProductClass = get_model('catalogue', 'ProductClass')
        return ProductClass.objects.get(slug='seat')

    def availability_policy(self, product, stockrecord):
        """ A product is unavailable for non-admin users if the current date is
        beyond the product's expiration date. Products are always available for admin users.
        """

        is_staff = getattr(self.user, 'is_staff', False)
        is_available = product.expires is None or (product.expires >= timezone.now())
        if is_staff or is_available:
            return super(CourseSeatAvailabilityPolicyMixin, self).availability_policy(product, stockrecord)
        else:
            return availability.Unavailable()


class DefaultStrategy(CourseSeatAvailabilityPolicyMixin,
                      strategy.NoTax, strategy.Structured):
    def __init__(self, request=None, user=None, site=None):
        super(DefaultStrategy, self).__init__()
        if request:
            user = user or getattr(request, 'user', None)
            site = site or getattr(request, 'site', None)

        self.request = request
        self.user = user
        self.site = site or Site.objects.get_current()
        self.partner = self.site.siteconfiguration.partner

    def select_stockrecord(self, product):
        try:
            return product.stockrecords.get(partner=self.partner)
        except Exception:
            return None


class Selector(object):
    def strategy(self, request=None, user=None, site=None):  # pylint: disable=unused-argument
        return DefaultStrategy(request, user, site)

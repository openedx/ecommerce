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
        """ A seat is unavailable if the current date is beyond the seat's expiration date. """
        if product.expires and timezone.now() > product.expires:
            return availability.Unavailable()

        return super(CourseSeatAvailabilityPolicyMixin, self).availability_policy(product, stockrecord)


class DefaultStrategy(strategy.UseFirstStockRecord, CourseSeatAvailabilityPolicyMixin,
                      strategy.NoTax, strategy.Structured):
    pass


class Selector(object):
    def strategy(self, request=None, user=None, **kwargs):  # pylint: disable=unused-argument
        return DefaultStrategy()



from django.utils import timezone
from oscar.apps.partner import availability, strategy
from oscar.core.loading import get_model

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME


class CourseSeatAvailabilityPolicyMixin(strategy.StockRequired):
    """
    Availability policy for Course seats.

    Child seats are only available if the current date is not beyond the seat's enrollment close date.
    Parent seats are never available.
    """

    @property
    def seat_class(self):
        ProductClass = get_model('catalogue', 'ProductClass')
        return ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME)

    def availability_policy(self, product, stockrecord):
        """ A product is unavailable for non-admin users if the current date is
        beyond the product's expiration date. Products are always available for admin users.
        """

        is_staff = getattr(self.user, 'is_staff', False)
        is_available = product.expires is None or (product.expires >= timezone.now())
        if is_staff or is_available:
            return super(CourseSeatAvailabilityPolicyMixin, self).availability_policy(product, stockrecord)

        return availability.Unavailable()


class DefaultStrategy(strategy.UseFirstStockRecord, CourseSeatAvailabilityPolicyMixin,
                      strategy.NoTax, strategy.Structured):
    """ Default Strategy """


class Selector:
    def strategy(self, request=None, user=None, **kwargs):  # pylint: disable=unused-argument
        return DefaultStrategy(request if hasattr(request, 'user') else None)

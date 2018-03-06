from oscar.core.loading import get_model
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.digital_books.utils import get_digital_book_bundle
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import SingleItemConsumptionConditionMixin

Condition = get_model('offer', 'Condition')


class DigitalBookBundleCondition(SingleItemConsumptionConditionMixin, Condition):
    class Meta(object):
        app_label = 'digital_books'
        proxy = True

    @property
    def name(self):
        return 'Basket contains every product in digital book bundle {}'.format(
            self.digital_book_bundle_uuid
        )

    @check_condition_applicability()
    def is_satisfied(self, offer, basket):
        # TODO: make docstring
        try:
            digital_book_bundle = get_digital_book_bundle(self.digital_book_bundle_uuid, basket.site.siteconfiguration)
        except (HttpNotFoundError, SlumberBaseException, Timeout):
            return False


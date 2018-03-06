from oscar.core.loading import get_model

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

    #TODO:
    #@check_condition_applicability
    #is_satisfied
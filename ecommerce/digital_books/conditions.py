from oscar.core.loading import get_model
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.digital_books.utils import get_digital_book_bundle
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import SingleItemConsumptionConditionMixin

import logging
logger = logging.getLogger(__name__)

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
        basket_skus = set([line.stockrecord.partner_sku for line in basket.all_lines()])
        try:
            digital_book_bundle = get_digital_book_bundle(self.digital_book_bundle_uuid, basket.site.siteconfiguration)
        except (HttpNotFoundError, SlumberBaseException, Timeout):
            return False

        # Get all of the skus of the course that satisfies this digital_book_bundle
        course_skus = set()

        # TODO: check for applicable seat types
        for course in digital_book_bundle['courses']:
            for course_runs in course['course_runs']:
                # TODO: test w/ course that has multiple course_runs
                course_skus.update(set([seat['sku'] for seat in course_runs['seats']]))

            # The lack of a difference in the set of SKUs in the basket and the course indicates that
            # that there is no intersection. Therefore, the basket contains no SKUs for the course.
            # It follows that the program condition is not met.
            diff = basket_skus.difference(course_skus)
            if diff == basket_skus:
                return False

            # If there is a difference between the basket SKUs and course SKUs, it represents the basket SKUs
            # minus the SKUs for the course. Since we have already verified the course is represented,
            # its SKUs can be safely removed from the set of SKUs in the basket being checked. Note that this
            # does NOT affect the actual basket, just our copy of its SKUs.
            basket_skus = diff

        # TODO: query discovery service for digital book sku - for now just hard code the book sku
        # TODO: make this be able to handle 0-n books
        digital_book_sku = '8528EDB'
        if digital_book_sku not in basket_skus:
            return False

        return True

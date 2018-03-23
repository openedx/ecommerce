"""
Checks that if a Basket Meets the Conditions of a Journal Bundle Offer
"""
import operator

from oscar.apps.offer import utils as oscar_utils
from oscar.core.loading import get_model
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import SingleItemConsumptionConditionMixin
from ecommerce.journal.client import fetch_journal_bundle

Condition = get_model('offer', 'Condition')


class JournalBundleCondition(SingleItemConsumptionConditionMixin, Condition):
    basket_skus = None
    journal_bundle = None

    class Meta(object):
        app_label = 'journal'
        proxy = True

    @property
    def name(self):
        return 'Basket contains every product in bundle {}'.format(self.journal_bundle_uuid)

    def get_applicable_course_skus(self, return_set=False):
        """
        Returns a dict of applicable SKUs for each course,
        unless return_set flag is set, then all skus are returned as one set

        """
        course_skus = {}
        if self.journal_bundle:
            applicable_seat_types = self.journal_bundle['applicable_seat_types']

            for course in self.journal_bundle['courses']:
                course_skus[course['key']] = set()
                for course_run in course['course_runs']:
                    course_skus[course['key']].update(
                        set([seat['sku'] for seat in course_run['seats'] if seat['type'] in applicable_seat_types])
                    )

        if return_set:
            sku_set = set()
            for course_sku_set in course_skus.values():
                sku_set.update(course_sku_set)

            course_skus = sku_set

        return course_skus

    def get_applicable_journal_skus(self):
        """ Returns set of journal SKUs to which this condition applies. """
        journal_skus = set()

        if self.journal_bundle:
            for journal in self.journal_bundle['journals']:
                journal_skus.update([journal['sku']])

        return journal_skus

    def basket_contains_all_required_courses(self):
        """
        Returns True if the basket contains SKUs for all required courses, if they have applicable seat types

        assumption: if a user is enrolled in a course we do not give them this discount
        """
        applicable_skus = self.get_applicable_course_skus()
        for course in self.journal_bundle['courses']:
            # If the basket has no SKUs left, but we still have courses over which to iterate,
            # the user cannot meet the condition that all courses be represented.
            if not self.basket_skus:
                return False

            # Get all of the SKUs that can satisfy this course
            skus = applicable_skus[course['key']]

            # The lack of a difference in the set of SKUs in the basket and the course indicates that
            # there is no intersection.  Therefore, the basket contains no SKUs for the current course.
            # It follows that the journal bundle condition is not met.
            diff = self.basket_skus.difference(skus)
            if diff == self.basket_skus:
                return False

            # If there is a difference between the basket SKUs and the course SKUs and course SKUs,
            # it represents the basket SKUs minus the SKUs for the current course.  Since we have already
            # verified the course is represented, its SKUs can be safely removed from the set of SKUs
            # in the basket being checked. (It does not affect the actual basket, just our copy)
            self.basket_skus = diff

        return True

    def basket_contains_all_journals(self):
        """
        Returns True if basket contains SKUs for all required journals
        """
        applicable_journal_skus = self.get_applicable_journal_skus()

        # In order for this condition to be applied all applicable journal skus must be present in the basket
        # in other words, the applicable skus must be a subset of the basket skus
        if applicable_journal_skus.issubset(self.basket_skus):
            return True

        return False

    @check_condition_applicability()
    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines if a user is eligible for a journal bundle offer based on the products in their basket.

        Args:
            basket: contains information on line items for order, associated siteconfiguration
                and associated user

        Returns:
            bool: True if condition is met
        """
        self.basket_skus = set([line.stockrecord.partner_sku for line in basket.all_lines()])
        try:
            self.journal_bundle = fetch_journal_bundle(
                site=basket.site,
                journal_bundle_uuid=self.journal_bundle_uuid
            )
        except (HttpNotFoundError, SlumberBaseException, Timeout):
            return False

        if not self.journal_bundle:
            return False

        if not self.basket_contains_all_required_courses():
            return False

        if not self.basket_contains_all_journals():
            return False

        return True

    def get_applicable_skus(self, site):
        """ Returns set of SKUs to which this condition applies. """
        journal_bundle_skus = set()
        self.journal_bundle = fetch_journal_bundle(
            site=site,
            journal_bundle_uuid=self.journal_bundle_uuid
        )

        journal_bundle_skus.update(self.get_applicable_course_skus(return_set=True))
        journal_bundle_skus.update(self.get_applicable_journal_skus())
        return journal_bundle_skus

    def can_apply_condition(self, line):
        """ Determines whether the condition can be applied to a given basket line. """
        if not line.stockrecord_id:
            return False

        product = line.product
        if line.stockrecord.partner_sku not in self.get_applicable_skus(line.basket.site):
            return False

        if not product.get_is_discountable():
            return False

        return True


    def get_applicable_lines(self, offer, basket, most_expensive_first=True):
        """ Return line data for the lines that can be consumed by this condition """
        line_tuples = []
        for line in basket.all_lines():
            if not self.can_apply_condition(line):
                continue

            price = oscar_utils.unit_price(offer, line)
            if not price:
                continue
            line_tuples.append((price, line))

        return sorted(line_tuples, reverse=most_expensive_first, key=operator.itemgetter(0))

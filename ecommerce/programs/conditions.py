

import logging
import operator

from django.conf import settings
from edx_django_utils.cache import TieredCache
from oscar.apps.offer import utils as oscar_utils
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.core.utils import deprecated_traverse_pagination, get_cache_key
from ecommerce.extensions.offer.decorators import check_condition_applicability
from ecommerce.extensions.offer.mixins import SingleItemConsumptionConditionMixin
from ecommerce.programs.utils import get_program

Condition = get_model('offer', 'Condition')
logger = logging.getLogger(__name__)


class ProgramCourseRunSeatsCondition(SingleItemConsumptionConditionMixin, Condition):
    class Meta:
        app_label = 'programs'
        proxy = True

    @property
    def name(self):
        return 'Basket contains a seat for every course in program {}'.format(self.program_uuid)

    def _get_applicable_skus(self, site_configuration):
        """ SKUs to which this condition applies. """
        program_skus = set()
        program = get_program(self.program_uuid, site_configuration)
        if program:
            applicable_seat_types = program['applicable_seat_types']

            for course in program['courses']:
                for course_run in course['course_runs']:
                    program_skus.update(
                        {seat['sku'] for seat in course_run['seats'] if seat['type'] in applicable_seat_types}
                    )
                for entitlement in course['entitlements']:
                    if entitlement['mode'].lower() in applicable_seat_types:
                        program_skus.add(entitlement['sku'])
        return program_skus

    def _get_lms_resource_for_user(self, basket, resource_name, endpoint):
        cache_key = get_cache_key(
            site_domain=basket.site.domain,
            resource=resource_name,
            username=basket.owner.username,
        )
        data_list_cached_response = TieredCache.get_cached_response(cache_key)
        if data_list_cached_response.is_found:
            return data_list_cached_response.value

        user = basket.owner.username
        try:
            data_list = endpoint.get(user=user) or []
            TieredCache.set_all_tiers(cache_key, data_list, settings.LMS_API_CACHE_TIMEOUT)
        except (ReqConnectionError, SlumberBaseException, Timeout) as exc:
            logger.error('Failed to retrieve %s : %s', resource_name, str(exc))
            data_list = []
        return data_list

    def _get_lms_resource(self, basket, resource_name, endpoint):
        if not basket.owner:
            return []
        return self._get_lms_resource_for_user(basket, resource_name, endpoint)

    def _get_user_ownership_data(self, basket, retrieve_entitlements=False):
        """
        Retrieves existing enrollments and entitlements for a user from LMS
        """
        enrollments = []
        entitlements = []

        site_configuration = basket.site.siteconfiguration
        if site_configuration.enable_partial_program:
            enrollments = self._get_lms_resource(
                basket, 'enrollments', site_configuration.enrollment_api_client.enrollment)
            if retrieve_entitlements:
                response = self._get_lms_resource(
                    basket, 'entitlements', site_configuration.entitlement_api_client.entitlements
                )
                if isinstance(response, dict):
                    entitlements = deprecated_traverse_pagination(
                        response, site_configuration.entitlement_api_client.entitlements)
                else:
                    entitlements = response
        return enrollments, entitlements

    def _has_entitlements(self, program):
        """
        Determines whether an entitlement product exists for any course in the program.
        """
        for course in program['courses']:
            if course['entitlements']:
                return True
        return False

    @check_condition_applicability()
    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines if a user is eligible for a program offer based on products in their basket
        and their existing course enrollments.

        Args:
            basket : contains information on line items for order, associated siteconfiguration
                        for retrieving program details, and associated user for retrieving enrollments
        Returns:
            bool
        """
        basket_skus = {line.stockrecord.partner_sku for line in basket.all_lines()}
        try:
            program = get_program(self.program_uuid, basket.site.siteconfiguration)
        except (HttpNotFoundError, SlumberBaseException, Timeout):
            return False

        if program and program['status'] == 'active':
            applicable_seat_types = program['applicable_seat_types']
        else:
            return False

        retrieve_entitlements = self._has_entitlements(program)
        enrollments, entitlements = self._get_user_ownership_data(basket, retrieve_entitlements)

        for course in program['courses']:
            # If the user is already enrolled in a course, we do not need to check their basket for it
            if any(enrollment['course_details']['course_id'] in [run['key'] for run in course['course_runs']] and
                   enrollment['mode'] in applicable_seat_types for enrollment in enrollments):
                continue
            if any(course['uuid'] == entitlement['course_uuid'] and
                   entitlement['mode'] in applicable_seat_types for entitlement in entitlements):
                continue

            # If the  basket has no SKUs left, but we still have courses over which
            # to iterate, the user cannot meet the condition that all courses be represented.
            if not basket_skus:
                return False

            # Get all of the SKUs that can satisfy this course
            skus = set()
            for course_run in course['course_runs']:
                skus.update({seat['sku'] for seat in course_run['seats'] if seat['type'] in applicable_seat_types})
            for entitlement in course['entitlements']:
                if entitlement['mode'].lower() in applicable_seat_types:
                    skus.add(entitlement['sku'])

            # The lack of a difference in the set of SKUs in the basket and the course indicates that
            # that there is no intersection. Therefore, the basket contains no SKUs for the current course.
            # Because the user is also not enrolled in the course, it follows that the program condition is not met.
            diff = basket_skus.difference(skus)
            if diff == basket_skus:
                return False

            # If there is a difference between the basket SKUs and course SKUs, it represents the basket SKUs
            # minus the SKUs for the current course. Since we have already verified the course is represented,
            # its SKUs can be safely removed from the set of SKUs in the basket being checked. Note that this
            # does NOT affect the actual basket, just our copy of its SKUs.
            basket_skus = diff

        return True

    def can_apply_condition(self, line):
        """ Determines whether the condition can be applied to a given basket line. """
        if not line.stockrecord_id:
            return False

        product = line.product
        return line.stockrecord.partner_sku in self._get_applicable_skus(
            line.basket.site.siteconfiguration) and product.get_is_discountable()

    def get_applicable_lines(self, offer, basket, most_expensive_first=True):
        """ Return line data for the lines that can be consumed by this condition. """
        line_tuples = []
        for line in basket.all_lines():
            if not self.can_apply_condition(line):
                continue

            price = oscar_utils.unit_price(offer, line)
            if not price:
                continue
            line_tuples.append((price, line))

        return sorted(line_tuples, reverse=most_expensive_first, key=operator.itemgetter(0))

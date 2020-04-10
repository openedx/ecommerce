from __future__ import absolute_import, unicode_literals

import logging
from uuid import UUID

import crum
from django.contrib import messages
from django.utils.translation import ugettext as _
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.enterprise.api import catalog_contains_course_runs
from ecommerce.enterprise.utils import get_enterprise_id_for_user
from ecommerce.extensions.basket.utils import ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
from ecommerce.extensions.offer.constants import OFFER_ASSIGNMENT_REVOKED, OFFER_REDEEMED
from ecommerce.extensions.offer.mixins import ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE
from ecommerce.extensions.offer.utils import get_benefit_type, get_discount_value

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferAssignment = get_model('offer', 'OfferAssignment')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
logger = logging.getLogger(__name__)


def is_offer_max_discount_available(basket, offer):
    # no need to do anything if this is not an enterprise offer or `max_discount` is not set
    if offer.priority != OFFER_PRIORITY_ENTERPRISE or offer.max_discount is None:
        return True

    # get course price
    product = basket.lines.first().product
    seat = product.course.seat_products.get(id=product.id)
    stock_record = StockRecord.objects.get(product=seat, partner=product.course.partner)
    course_price = stock_record.price_excl_tax

    # calculate discount value that will be covered by the offer
    benefit_type = get_benefit_type(offer.benefit)
    benefit_value = float(offer.benefit.value)
    if benefit_type == Benefit.PERCENTAGE:
        discount_value = get_discount_value(benefit_value, float(course_price))
    else:  # Benefit.FIXED
        # There is a possibility that the discount value could be greater than the course price
        # ie, discount value is $100, course price is $75, in this case the full price of the course will be covered
        # and learner will owe $0 to checkout.
        if benefit_value > course_price:
            discount_value = course_price
        else:
            discount_value = benefit_value

    # check if offer has discount available
    new_total_discount = discount_value + offer.total_discount
    if new_total_discount <= offer.max_discount:
        return True

    return False


class EnterpriseCustomerCondition(ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin, Condition):
    class Meta:
        app_label = 'enterprise'
        proxy = True

    @property
    def name(self):
        return "Basket contains a seat from {}'s catalog".format(self.enterprise_customer_name)

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines if a user is eligible for an enterprise customer offer
        based on their association with the enterprise customer.

        It also filter out the offer if the `enterprise_customer_catalog_uuid`
        value set on the offer condition does not match with the basket catalog
        value when explicitly provided by the enterprise learner.

        Note: Currently there is no mechanism to prioritize or apply multiple
        offers that may apply as opposed to disqualifying offers if the
        catalog doesn't explicitly match.

        Arguments:
            basket (Basket): Contains information about order line items, the current site,
                             and the user attempting to make the purchase.
        Returns:
            bool
        """
        if not basket.owner:
            # An anonymous user is never linked to any EnterpriseCustomer.
            return False

        enterprise_customer = str(self.enterprise_customer_uuid)
        enterprise_catalog = str(self.enterprise_customer_catalog_uuid)
        username = basket.owner.username
        course_run_ids = []
        for line in basket.all_lines():
            course = line.product.course
            if not course:
                # Basket contains products not related to a course_run.
                # Only log for non-site offers to avoid noise.
                if offer.offer_type != ConditionalOffer.SITE:
                    logger.warning('[Code Redemption Failure] Unable to apply enterprise offer because '
                                   'the Basket contains a product not related to a course_run. '
                                   'User: %s, Offer: %s, Product: %s, Enterprise: %s, Catalog: %s',
                                   username,
                                   offer.id,
                                   line.product.id,
                                   enterprise_customer,
                                   enterprise_catalog)
                return False

            course_run_ids.append(course.id)

        courses_in_basket = ','.join(course_run_ids)
        enterprise_id = get_enterprise_id_for_user(basket.site, basket.owner)
        if enterprise_id and enterprise_customer != enterprise_id:
            # Learner is not linked to the EnterpriseCustomer associated with this condition.
            if offer.offer_type == ConditionalOffer.VOUCHER:
                logger.warning('[Code Redemption Failure] Unable to apply enterprise offer because Learner\'s '
                               'enterprise (%s) does not match this conditions\'s enterprise (%s). '
                               'User: %s, Offer: %s, Enterprise: %s, Catalog: %s, Courses: %s',
                               enterprise_id,
                               enterprise_customer,
                               username,
                               offer.id,
                               enterprise_customer,
                               enterprise_catalog,
                               courses_in_basket)
            return False

        # Verify that the current conditional offer is related to the provided
        # enterprise catalog, this will also filter out offers which don't
        # have `enterprise_customer_catalog_uuid` value set on the condition.
        catalog = self._get_enterprise_catalog_uuid_from_basket(basket)
        if catalog:
            if offer.condition.enterprise_customer_catalog_uuid != catalog:
                logger.warning('Unable to apply enterprise offer %s because '
                               'Enterprise catalog id on the basket (%s) '
                               'does not match the catalog for this condition (%s).',
                               offer.id, catalog, offer.condition.enterprise_customer_catalog_uuid)
                return False

        try:
            catalog_contains_course = catalog_contains_course_runs(
                basket.site, course_run_ids, enterprise_customer, enterprise_customer_catalog_uuid=enterprise_catalog,
                request=basket.strategy.request
            )
        except (ReqConnectionError, KeyError, SlumberHttpBaseException, Timeout) as exc:
            logger.exception('[Code Redemption Failure] Unable to apply enterprise offer because '
                             'we failed to check if course_runs exist in the catalog. '
                             'User: %s, Offer: %s, Message: %s, Enterprise: %s, Catalog: %s, Courses: %s',
                             username,
                             offer.id,
                             exc,
                             enterprise_customer,
                             enterprise_catalog,
                             courses_in_basket)
            return False

        if not catalog_contains_course:
            # Basket contains course runs that do not exist in the EnterpriseCustomerCatalogs
            # associated with the EnterpriseCustomer.
            logger.warning('[Code Redemption Failure] Unable to apply enterprise offer because '
                           'Enterprise catalog does not contain the course(s) in this basket. '
                           'User: %s, Offer: %s, Enterprise: %s, Catalog: %s, Courses: %s',
                           username,
                           offer.id,
                           enterprise_customer,
                           enterprise_catalog,
                           courses_in_basket)
            return False

        if not is_offer_max_discount_available(basket, offer):
            logger.warning(
                '[Enterprise Offer Failure] Unable to apply enterprise offer because bookings limit is consumed.'
                'User: %s, Offer: %s, Enterprise: %s, Catalog: %s, Courses: %s, BookingsLimit: %s, TotalDiscount: %s',
                username,
                offer.id,
                enterprise_customer,
                enterprise_catalog,
                courses_in_basket,
                offer.max_discount,
                offer.total_discount,
            )
            return False

        return True

    @staticmethod
    def _get_enterprise_catalog_uuid_from_basket(basket):
        """
        Helper method for fetching valid enterprise catalog UUID from basket.

        Arguments:
             basket (Basket): The provided basket can be either temporary (just
             for calculating discounts) or an actual one to buy a product.
        """
        # For temporary basket try to get `catalog` from request
        catalog = basket.strategy.request.GET.get(
            'catalog'
        ) if basket.strategy.request else None

        if not catalog:
            # For actual baskets get `catalog` from basket attribute
            enterprise_catalog_attribute, __ = BasketAttributeType.objects.get_or_create(
                name=ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
            )
            enterprise_customer_catalog = BasketAttribute.objects.filter(
                basket=basket,
                attribute_type=enterprise_catalog_attribute,
            ).first()
            if enterprise_customer_catalog:
                catalog = enterprise_customer_catalog.value_text

        # Return only valid UUID
        try:
            catalog = UUID(catalog) if catalog else None
        except ValueError:
            catalog = None

        return catalog


class AssignableEnterpriseCustomerCondition(EnterpriseCustomerCondition):
    """An enterprise condition that can be redeemed by one or more assigned users."""
    class Meta:
        app_label = 'enterprise'
        proxy = True

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        Determines that if user has assigned a voucher and is eligible for redeem it.

        Arguments:
            offer (ConditionalOffer): The offer to be redeemed.
            basket (Basket): The basket of products being purchased.

        Returns:
            bool
        """
        condition_satisfied = super(AssignableEnterpriseCustomerCondition, self).is_satisfied(offer, basket)
        if condition_satisfied is False:
            return False

        voucher = basket.vouchers.first()

        # get assignments for the basket owner and basket voucher
        user_with_code_assignments = OfferAssignment.objects.filter(
            code=voucher.code, user_email=basket.owner.email
        ).exclude(
            status__in=[OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]
        )

        # user has assignments available
        if user_with_code_assignments.exists():
            return True

        # basket owner can redeem the voucher if free slots are avialable
        if voucher.slots_available_for_assignment:
            return True

        messages.warning(
            crum.get_current_request(),
            _('This code is not valid with your email. '
              'Please login with the correct email assigned '
              'to the code or contact your Learning Manager '
              'for additional questions.'),
        )

        logger.warning('[Code Redemption Failure] Unable to apply enterprise offer because '
                       'the voucher has not been assigned to this user and their are no remaining available uses. '
                       'User: %s, Offer: %s, Enterprise: %s, Catalog: %s',
                       basket.owner.username,
                       offer.id,
                       self.enterprise_customer_uuid,
                       self.enterprise_customer_catalog_uuid)

        return False

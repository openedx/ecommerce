

import logging
from decimal import Decimal
from uuid import UUID

import crum
from django.contrib import messages
from django.db.models import Sum
from django.utils.translation import ugettext as _
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.courses.utils import get_course_info_from_catalog
from ecommerce.enterprise.api import catalog_contains_course_runs, get_enterprise_id_for_user
from ecommerce.enterprise.utils import get_or_create_enterprise_customer_user
from ecommerce.extensions.basket.utils import ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
from ecommerce.extensions.fulfillment.status import ORDER
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
Order = get_model('order', 'Order')
OrderDiscount = get_model('order', 'OrderDiscount')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
logger = logging.getLogger(__name__)


def is_offer_max_user_discount_available(basket, offer):
    """Calculate if the user has the per user discount amount available"""
    # no need to do anything if this is not an enterprise offer or `user_max_discount` is not set
    if offer.priority != OFFER_PRIORITY_ENTERPRISE or offer.max_user_discount is None:
        return True
    discount_value = _get_basket_discount_value(basket, offer)
    # check if offer has discount available for user
    sum_user_discounts_for_this_offer = OrderDiscount.objects.filter(
        offer_id=offer.id, order__user_id=basket.owner.id, order__status=ORDER.COMPLETE
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal(0.00)
    new_total_discount = discount_value + sum_user_discounts_for_this_offer
    if new_total_discount <= offer.max_user_discount:
        return True

    return False


def is_offer_max_discount_available(basket, offer):
    """Calculate if the offer has available discount"""
    # no need to do anything if this is not an enterprise offer or `max_discount` is not set
    if offer.priority != OFFER_PRIORITY_ENTERPRISE or offer.max_discount is None:
        return True
    discount_value = _get_basket_discount_value(basket, offer)
    # check if offer has discount available
    new_total_discount = discount_value + offer.total_discount
    if new_total_discount <= offer.max_discount:
        return True

    return False


def _get_basket_discount_value(basket, offer):
    """Calculate the discount value based on benefit type and value"""
    sum_basket_lines = basket.all_lines().aggregate(total=Sum('stockrecord__price_excl_tax'))['total'] or Decimal(0.0)
    # calculate discount value that will be covered by the offer
    benefit_type = get_benefit_type(offer.benefit)
    benefit_value = offer.benefit.value
    if benefit_type == Benefit.PERCENTAGE:
        discount_value = get_discount_value(float(offer.benefit.value), float(sum_basket_lines))
        discount_value = Decimal(discount_value)
    else:  # Benefit.FIXED
        # There is a possibility that the discount value could be greater than the sum of basket lines
        # ie, discount value is $100, basket lines are $75, in this case the full price of the basket lines
        # will be covered and learner will owe $0 to checkout.
        if benefit_value > sum_basket_lines:
            discount_value = sum_basket_lines
        else:
            discount_value = benefit_value
    return discount_value


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

        enterprise_in_condition = str(self.enterprise_customer_uuid)
        enterprise_catalog = str(self.enterprise_customer_catalog_uuid) if self.enterprise_customer_catalog_uuid \
            else None
        enterprise_name_in_condition = str(self.enterprise_customer_name)
        username = basket.owner.username

        # This variable will hold both course keys and course run identifiers.
        course_ids = []
        for line in basket.all_lines():
            if line.product.is_course_entitlement_product:
                try:
                    response = get_course_info_from_catalog(basket.site, line.product)
                except (ReqConnectionError, KeyError, SlumberHttpBaseException, Timeout) as exc:
                    logger.exception(
                        '[Code Redemption Failure] Unable to apply enterprise offer because basket '
                        'contains a course entitlement product but we failed to get course info from  '
                        'course entitlement product.'
                        'User: %s, Offer: %s, Message: %s, Enterprise: %s, Catalog: %s, Course UUID: %s',
                        username,
                        offer.id,
                        exc,
                        enterprise_in_condition,
                        enterprise_catalog,
                        line.product.attr.UUID
                    )
                    return False
                else:
                    course_ids.append(response['key'])

                    # Skip to the next iteration.
                    continue

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
                                   enterprise_in_condition,
                                   enterprise_catalog)
                return False

            course_ids.append(course.id)

        courses_in_basket = ','.join(course_ids)
        user_enterprise = get_enterprise_id_for_user(basket.site, basket.owner)
        if user_enterprise and enterprise_in_condition != user_enterprise:
            # Learner is not linked to the EnterpriseCustomer associated with this condition.
            if offer.offer_type == ConditionalOffer.VOUCHER:
                logger.warning('[Code Redemption Failure] Unable to apply enterprise offer because Learner\'s '
                               'enterprise (%s) does not match this conditions\'s enterprise (%s). '
                               'User: %s, Offer: %s, Enterprise: %s, Catalog: %s, Courses: %s',
                               user_enterprise,
                               enterprise_in_condition,
                               username,
                               offer.id,
                               enterprise_in_condition,
                               enterprise_catalog,
                               courses_in_basket)

                logger.info(
                    '[Code Redemption Issue] Linking learner with the enterprise in Condition. '
                    'User [%s], Enterprise [%s]',
                    username,
                    enterprise_in_condition
                )
                get_or_create_enterprise_customer_user(
                    basket.site,
                    enterprise_in_condition,
                    username,
                    False
                )
                msg = _('This coupon has been made available through {new_enterprise}. '
                        'To redeem this coupon, you must first logout. When you log back in, '
                        'please select {new_enterprise} as your enterprise '
                        'and try again.').format(new_enterprise=enterprise_name_in_condition)
                messages.warning(crum.get_current_request(), msg,)

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
                basket.site, course_ids, enterprise_in_condition,
                enterprise_customer_catalog_uuid=enterprise_catalog
            )
        except (ReqConnectionError, KeyError, SlumberHttpBaseException, Timeout) as exc:
            logger.exception('[Code Redemption Failure] Unable to apply enterprise offer because '
                             'we failed to check if course_runs exist in the catalog. '
                             'User: %s, Offer: %s, Message: %s, Enterprise: %s, Catalog: %s, Courses: %s',
                             username,
                             offer.id,
                             exc,
                             enterprise_in_condition,
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
                           enterprise_in_condition,
                           enterprise_catalog,
                           courses_in_basket)
            return False

        if not is_offer_max_discount_available(basket, offer):
            logger.warning(
                '[Enterprise Offer Failure] Unable to apply enterprise offer because bookings limit is consumed.'
                'User: %s, Offer: %s, Enterprise: %s, Catalog: %s, Courses: %s, BookingsLimit: %s, TotalDiscount: %s',
                username,
                offer.id,
                enterprise_in_condition,
                enterprise_catalog,
                courses_in_basket,
                offer.max_discount,
                offer.total_discount,
            )
            return False

        if not is_offer_max_user_discount_available(basket, offer):
            logger.warning(
                '[Enterprise Offer Failure] Unable to apply enterprise offer because user bookings limit is consumed.'
                'User: %s, Offer: %s, Enterprise: %s, Catalog: %s, Courses: %s, UserBookingsLimit: %s',
                username,
                offer.id,
                enterprise_in_condition,
                enterprise_catalog,
                courses_in_basket,
                offer.max_user_discount
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

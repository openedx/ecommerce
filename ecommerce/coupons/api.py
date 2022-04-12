
import logging
from types import SimpleNamespace
from ecommerce.extensions.payment.utils import embargo_check

import newrelic.agent
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from edx_rest_api_client.client import EdxRestApiClient
from oscar.core.loading import get_class, get_model

from ecommerce.coupons.applicator import Applicator
from ecommerce.coupons.constants import COURSE_MODES_RANKING
from ecommerce.coupons.exceptions import RedeemCouponError
from ecommerce.coupons.utils import is_voucher_applied
from ecommerce.courses.utils import get_course_detail
from ecommerce.enterprise.exceptions import EnterpriseDoesNotExist
from ecommerce.enterprise.utils import get_enterprise_customer_from_voucher
from ecommerce.extensions.analytics.utils import audit_log
from ecommerce.extensions.basket.utils import (
    _set_basket_bundle_status,
    apply_voucher_on_basket_and_check_discount,
    basket_add_enterprise_catalog_attribute,
    is_duplicate_seat_attempt
)
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder

logger = logging.getLogger(__name__)

User = get_user_model()
Voucher = get_model('voucher', 'Voucher')
StockRecord = get_model('partner', 'StockRecord')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Selector = get_class('partner.strategy', 'Selector')
post_checkout = get_class('checkout.signals', 'post_checkout')


class CustomEdxOrderPlacementMixin(EdxOrderPlacementMixin):
    def handle_successful_order(self, order, request=None):  # pylint: disable=arguments-differ
        """
        Send a signal so that receivers can perform relevant tasks (e.g., fulfill the order).

        Sends an additional `create_consent_record` param with the signal so that a data-sharing
        consent is not created for the user during enrollment.
        """
        audit_log(
            'order_placed',
            amount=order.total_excl_tax,
            basket_id=order.basket.id,
            currency=order.currency,
            order_number=order.number,
            user_id=order.user.id,
            contains_coupon=order.contains_coupon
        )

        # create offer assignment for MULTI_USE_PER_CUSTOMER
        self.create_assignments_for_multi_use_per_customer(order)

        # update offer assignment with voucher application
        self.update_assigned_voucher_offer_assignment(order)

        post_checkout.send(
            sender=self,
            order=order,
            request=request,
            email_opt_in=False,  # Do not send users fulfillment emails
            create_consent_record=False  # Do not create consent record for user
        )

        return order


class CouponCodeRedeemer(CustomEdxOrderPlacementMixin):
    """
    Allows a coupon code to be redeemed to enroll a user into a course.
    """

    def __init__(self, site=None):
        if site:
            self.site = site
        else:
            # TODO: Figure out the best way to get default, i.e.
            # Site.objects.get(domain=learner['enterprise_customer']['site']['domain']) == request.site
            self.site = Site.objects.first()

        super().__init__()

    def _is_voucher_valid(self, voucher, products, user):
        """
        Check if the voucher is valid.
        """

        if not voucher.is_active():
            return False, 'This coupon code is not active.'

        is_available, msg = voucher.is_available_to_user(user)
        if not is_available:
            return False, msg

        if len(products) == 1:
            purchase_info = Selector().strategy(user=user).fetch_for_product(products[0])

            if not purchase_info.availability.is_available_to_buy:
                return False, 'This product is not available for purchase.'

        offer = voucher.best_offer
        if offer.get_max_applications(user) == 0:
            return False, 'This coupon code is no longer available.'

        return True, ''

    def _get_highest_ranking_seat(self, seats):
        """
        Gets the highest ranking seat for a course run.
        """
        if not seats:
            return None

        seats_sorted_by_rank = sorted(seats, key=lambda seat: COURSE_MODES_RANKING[seat['type']])
        return seats_sorted_by_rank[0]

    def _get_sku_for_course(self, course_id):
        """
        Get the sku of the product to apply the voucher against.
        """
        try:
            course_detail = get_course_detail(self.site, course_id)
            course_runs = course_detail['course_runs']
        except Exception as ex:
            logger.exception('[Code Redemption Failure] Could not fetch course detail for %s', course_id)
            raise RedeemCouponError from ex

        # TODO: handle active/upcoming/not enrollable course runs
        course_run_to_enroll_in = course_runs[0]
        seats = course_run_to_enroll_in['seats']
        highest_ranking_seat = self._get_highest_ranking_seat(seats)

        sku = highest_ranking_seat['sku']

        return sku

    def _get_user_details(self, user):
        """
        Get details of the user from the LMS.
        """
        user_api_client = EdxRestApiClient(
            self.site.siteconfiguration.build_lms_url('/api/user/v1/'),
            jwt=self.site.siteconfiguration.access_token,
            append_slash=False
        )

        try:
            return user_api_client.accounts.get(lms_user_id=user.lms_user_id)[0]
        except Exception:
            logger.exception('[Code Redemption Failure] Could not fetch user details for user %s', user)
            raise

    @newrelic.agent.function_trace()
    def _prepare_basket(self, user, site, product, voucher, enterprise_customer_uuid):
        """
        Create or get the basket, adds the product, and applies the voucher.
        """

        basket = Basket.get_basket(user, site)

        # set enterprise_customer_uuid on basket so that it's accessible
        # in all contexts
        setattr(basket, 'enterprise_customer_uuid', enterprise_customer_uuid)

        # normally the enterprise catalog UUID attribute is added on basket
        basket_add_enterprise_catalog_attribute(basket, {})
        basket.flush()
        basket.save()

        # We won't support bundle for this flow
        bundle = None
        basket_addition = get_class('basket.signals', 'basket_addition')
        already_purchased_products = []
        _set_basket_bundle_status(bundle, basket)

        if self.site.siteconfiguration.enable_embargo_check:
            if not embargo_check(user, site, [product]):
                logger.warning(
                    'User %s blocked by embargo check, not adding products to basket',
                    user
                )
                return basket

        if is_duplicate_seat_attempt(basket, product):
            return basket

        if product.is_enrollment_code_product or \
                not UserAlreadyPlacedOrder.user_already_placed_order(
                    user=user,
                    product=product,
                    site=site
                ):
            basket.add_product(product, 1)
            # Call signal handler to notify listeners that something has been added to the basket
            basket_addition.send(
                sender=basket_addition,
                product=product,
                user=user,
                request=None,
                basket=basket,
                is_multi_product_basket=False
            )
        else:
            already_purchased_products.append(product)

        if already_purchased_products and basket.is_empty:
            raise AlreadyPlacedOrderException

        basket.clear_vouchers()

        if basket.total_excl_tax == 0:
            logger.exception(
                '[Code Redemption Failure] Basket total is already 0. User: %s, Code: %s.',
                user, voucher.code
            )
            raise RedeemCouponError

        apply_voucher_on_basket_and_check_discount(
            voucher,
            SimpleNamespace(user=user),
            basket,
            Applicator
        )

        return basket

    def redeem_coupon_code(self, code, course_id, lms_user_id):

        error_msg_template = '[Code Redemption Failure] %s User: %s, Code: %s, Course: %s.'

        # User must exist at this point
        user = User.objects.get(lms_user_id=lms_user_id)

        try:
            voucher = Voucher.objects.get(code=code)
        except Voucher.DoesNotExist as ex:
            logger.exception(error_msg_template, 'No voucher found with code.', user, course_id, lms_user_id)
            raise RedeemCouponError from ex

        sku = self._get_sku_for_course(course_id)

        try:
            product = StockRecord.objects.get(partner_sku=sku).product
        except StockRecord.DoesNotExist as ex:
            logger.exception(error_msg_template, 'Product does not exist.', user, course_id, lms_user_id)
            raise RedeemCouponError from ex

        voucher_is_valid, invalid_voucher_message = self._is_voucher_valid(voucher, [product], user)

        if not voucher_is_valid:
            logger.exception(error_msg_template, invalid_voucher_message, user, course_id, lms_user_id)
            raise RedeemCouponError

        offer = voucher.best_offer

        user_details = self._get_user_details(user)

        if not offer.is_email_valid(user_details['email']):
            logger.exception(
                error_msg_template,
                'User email does not meet domain requirements.', user, course_id, lms_user_id
            )
            raise RedeemCouponError

        if not user_details['is_active']:
            logger.exception(error_msg_template, 'User is not active.', user, course_id, lms_user_id)
            raise RedeemCouponError

        try:
            enterprise_customer = get_enterprise_customer_from_voucher(self.site, voucher)
        except EnterpriseDoesNotExist as ex:
            logger.exception(
                error_msg_template,
                'Could not find matching enterprise customer.', user, course_id, lms_user_id
            )
            raise RedeemCouponError from ex

        if product.is_course_entitlement_product:
            logger.exception(
                error_msg_template,
                'This coupon is not valid for purchasing a program.', user, course_id, lms_user_id
            )
            raise RedeemCouponError

        try:
            basket = self._prepare_basket(
                user,
                self.site,
                product,
                voucher,
                (enterprise_customer or {}).get('id')
            )
        except AlreadyPlacedOrderException as ex:
            logger.exception(
                error_msg_template,
                'User has already purchased coursed.', user, course_id, lms_user_id
            )
            raise RedeemCouponError from ex

        if basket.total_excl_tax == 0:
            try:
                self.place_free_order(basket)
            except Exception as ex:  # pylint: disable=bare-except
                logger.exception(
                    error_msg_template,
                    'Failed to create a free order for basket.', user, course_id, lms_user_id
                )
                raise RedeemCouponError from ex
        else:
            logger.exception(
                error_msg_template,
                'Total cost was not 0 after applying coupon.', user, course_id, lms_user_id
            )
            raise RedeemCouponError

        if is_voucher_applied(basket, voucher):
            logger.info('Code %s successfully redeemed for user %s for course %s.', code, user, course_id)
        else:
            logger.exception(
                error_msg_template,
                'Failed to redeem coupon.', user, course_id, lms_user_id
            )
            basket.vouchers.remove(voucher)

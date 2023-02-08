

import datetime
import json
import logging
from urllib.parse import unquote, urlencode

import newrelic.agent
import pytz
import waffle
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from oscar.apps.basket.signals import voucher_addition
from oscar.core.loading import get_class, get_model

from ecommerce.core.url_utils import absolute_url
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.basket.constants import (
    EMAIL_OPT_IN_ATTRIBUTE,
    ENABLE_STRIPE_PAYMENT_PROCESSOR,
    PAYMENT_INTENT_ID_ATTRIBUTE,
    PURCHASER_BEHALF_ATTRIBUTE,
    REDIRECT_WITH_WAFFLE_TESTING_QUERYSTRING
)
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.payment.constants import DISABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME
from ecommerce.extensions.payment.utils import embargo_check
from ecommerce.programs.utils import get_program
from ecommerce.referrals.models import Referral

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
BUNDLE = 'bundle_identifier'
ORGANIZATION_ATTRIBUTE_TYPE = 'organization'
ENTERPRISE_CATALOG_ATTRIBUTE_TYPE = 'enterprise_catalog_uuid'
StockRecord = get_model('partner', 'StockRecord')
OrderLine = get_model('order', 'Line')
Refund = get_model('refund', 'Refund')
Voucher = get_model('voucher', 'Voucher')

logger = logging.getLogger(__name__)


def add_stripe_flag_to_url(url, request):
    """
    Add value of ENABLE_STRIPE_PAYMENT_PROCESSOR to url if REDIRECT_WITH_WAFFLE_TESTING_QUERYSTRING is on.
    """
    if not waffle.flag_is_active(
        request,
        REDIRECT_WITH_WAFFLE_TESTING_QUERYSTRING
    ):
        return url

    flag_name = ENABLE_STRIPE_PAYMENT_PROCESSOR
    flag_is_active = waffle.flag_is_active(
        request,
        flag_name
    )

    flag = 'dwft_{}={}'.format(flag_name, 1 if flag_is_active else 0)
    join = '&' if '?' in url else '?'
    return '{url}{join}{flag}'.format(
        url=url,
        join=join,
        flag=flag,
    )


def get_payment_microfrontend_or_basket_url(request):
    url = get_payment_microfrontend_url_if_configured(request)
    if not url:
        url = absolute_url(request, 'basket:summary')
    return url


def get_payment_microfrontend_url_if_configured(request):
    if _use_payment_microfrontend(request):
        return request.site.siteconfiguration.payment_microfrontend_url

    return None


def _use_payment_microfrontend(request):
    """
    Return whether the current request should use the payment MFE.
    """
    return (
        request.site.siteconfiguration.enable_microfrontend_for_basket_page and
        request.site.siteconfiguration.payment_microfrontend_url and
        not waffle.flag_is_active(request, DISABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME)
    )


@newrelic.agent.function_trace()
def add_utm_params_to_url(url, params):
    # utm_params is [(u'utm_content', u'course-v1:IDBx IDB20.1x 1T2017'),...
    utm_params = [item for item in params if 'utm_' in item[0]]
    # utm_params is utm_content=course-v1%3AIDBx+IDB20.1x+1T2017&...
    utm_params = urlencode(utm_params, True)
    # utm_params is utm_content=course-v1:IDBx+IDB20.1x+1T2017&...
    # (course-keys do not have url encoding)
    utm_params = unquote(utm_params)
    url = url + '?' + utm_params if utm_params else url
    return url


@newrelic.agent.function_trace()
def add_invalid_code_message_to_url(url, code):
    if code:
        message = 'error_message=Code {code} is invalid.'.format(code=str(code))
        url += '&' + message if '?' in url else '?' + message
    return url


@newrelic.agent.function_trace()
def prepare_basket(request, products, voucher=None):
    """
    Create or get the basket, add products, apply a voucher, and record referral data.

    Existing baskets are merged. Specified products will
    be added to the remaining open basket. If voucher is passed, all existing
    vouchers added to the basket are removed because we allow only one voucher per basket.
    Vouchers are not applied if an enrollment code product is in the basket.

    Arguments:
        request (Request): The request object made to the view.
        products (List): List of products to be added to the basket.
        voucher (Voucher): Voucher to apply to the basket.

    Returns:
        basket (Basket): Contains the product to be redeemed and the Voucher applied.
    """
    basket = Basket.get_basket(request.user, request.site)
    basket_add_enterprise_catalog_attribute(basket, request.GET)
    basket.flush()
    basket.save()
    basket_addition = get_class('basket.signals', 'basket_addition')
    already_purchased_products = []
    bundle = request.GET.get('bundle')

    _set_basket_bundle_status(bundle, basket)

    if request.site.siteconfiguration.enable_embargo_check:
        if not embargo_check(request.user, request.site, products):
            messages.error(
                request,
                _('Due to export controls, we cannot allow you to access this course at this time.')
            )
            logger.warning(
                'User [%s] blocked by embargo check, not adding products to basket',
                request.user.username
            )
            return basket

    is_multi_product_basket = len(products) > 1
    for product in products:
        # Multiple clicks can try adding twice, return if product is seat already in basket
        if is_duplicate_seat_attempt(basket, product):
            logger.info(
                'User [%s] repeated request to add [%s] seat of course [%s], will ignore',
                request.user.username,
                mode_for_product(product),
                product.course_id
            )
            return basket

        if product.is_enrollment_code_product or \
                not UserAlreadyPlacedOrder.user_already_placed_order(user=request.user,
                                                                     product=product, site=request.site):
            basket.add_product(product, 1)
            # Call signal handler to notify listeners that something has been added to the basket
            basket_addition.send(sender=basket_addition, product=product, user=request.user, request=request,
                                 basket=basket, is_multi_product_basket=is_multi_product_basket)
        else:
            already_purchased_products.append(product)
            logger.warning(
                'User [%s] attempted to repurchase the [%s] seat of course [%s]',
                request.user.username,
                mode_for_product(product),
                product.course_id
            )
    if already_purchased_products and basket.is_empty:
        raise AlreadyPlacedOrderException

    # Waiting to check and send segment event until after products are added into the basket
    # just in case the AlreadyPlacedOrderException is raised
    if bundle:
        program = get_program(bundle, request.site.siteconfiguration)
        bundle_properties = {
            'bundle_id': bundle,
            'cart_id': basket.id,
            'title': program.get('title'),
            'total_price': basket.total_excl_tax,
            'quantity': basket.lines.count(),
        }
        if program.get('type_attrs', {}).get('slug') and program.get('marketing_slug'):
            bundle_properties['marketing_slug'] = program['type_attrs']['slug'] + '/' + program.get('marketing_slug')
        track_segment_event(request.site, request.user, 'edx.bi.ecommerce.basket.bundle_added', bundle_properties)

    if len(products) == 1 and products[0].is_enrollment_code_product:
        basket.clear_vouchers()
    elif voucher or basket.vouchers.exists():
        voucher = voucher or basket.vouchers.first()
        basket.clear_vouchers()
        is_valid, message = validate_voucher(voucher, request.user, basket, request.site)
        if is_valid:
            apply_voucher_on_basket_and_check_discount(voucher, request, basket)
        else:
            logger.warning('[Code Redemption Failure] The voucher is not valid for this basket. '
                           'User: %s, Basket: %s, Code: %s, Message: %s',
                           request.user.username, request.basket.id, voucher.code, message)

    attribute_cookie_data(basket, request)
    return basket


@newrelic.agent.function_trace()
def get_basket_switch_data(product):
    """
    Given a seat or enrollment product, find the SKU of the related product of
    the other type, along with the text to display to the user for the
    toggle link.  This is used on the Basket Summary page to enable users to
    switch between purchasing a single course run Seat and making a bulk
    purchase of a set of Enrollment Codes for the same course run.

    Arguments:
        product (Product): Product of type Seat or Enrollment Code

    Returns:
        tuple(str, str): containing the link display text and associated sku
    """
    switch_link_text = None
    partner_sku = None

    if product.is_enrollment_code_product:
        partner_sku = _find_seat_enrollment_toggle_sku(product, 'child')
        switch_link_text = _('Click here to just purchase an enrollment for yourself')
    elif product.is_seat_product:
        partner_sku = _find_seat_enrollment_toggle_sku(product, 'standalone')
        switch_link_text = _('Click here to purchase multiple seats in this course')

    return switch_link_text, partner_sku


@newrelic.agent.function_trace()
def _find_seat_enrollment_toggle_sku(product, target_structure):
    """
    Given a seat or enrollment code product, find the SKU of the related product of
    the other type that matches the target structure.

    Arguments:
        product (Product): Product of type Seat or Enrollment Code
        target_structure (str): Structure of the related product we're seeking

    Returns:
        sku (str): The sku of the associated Seat or Enrollment Code product.
    """

    # Note: This query filter will not perform well with products that do not have a course_id
    stock_records = StockRecord.objects.filter(
        product__course_id=product.course_id,
        product__structure=target_structure
    )

    # Determine the proper partner SKU to embed in the single/multiple basket switch link
    # The logic here is a little confusing.  "Seat" products have "certificate_type" attributes, and
    # "Enrollment Code" products have "seat_type" attributes.  If the basket is in single-purchase
    # mode, we are working with a Seat product and must present the 'buy multiple' switch link and
    # SKU from the corresponding Enrollment Code product.  If the basket is in multi-purchase mode,
    # we are working with an Enrollment Code product and must present the 'buy single' switch link
    # and SKU from the corresponding Seat product.
    product_cert_type = getattr(product.attr, 'certificate_type', None)
    product_seat_type = getattr(product.attr, 'seat_type', None)
    for stock_record in stock_records:
        stock_record_cert_type = getattr(stock_record.product.attr, 'certificate_type', None)
        stock_record_seat_type = getattr(stock_record.product.attr, 'seat_type', None)
        if (product_seat_type and product_seat_type == stock_record_cert_type) or \
                (product_cert_type and product_cert_type == stock_record_seat_type):
            return stock_record.partner_sku

    return None


@newrelic.agent.function_trace()
def attribute_cookie_data(basket, request):
    try:
        with transaction.atomic():
            # If an exception is raised below, this nested atomic block prevents the
            # outer transaction created by ATOMIC_REQUESTS from being rolled back.
            referral = _referral_from_basket_site(basket, request.site)

            _record_affiliate_basket_attribution(referral, request)
            _record_utm_basket_attribution(referral, request)

            # Save the record if any attribution attributes are set on it.
            if any([getattr(referral, attribute) for attribute in Referral.ATTRIBUTION_ATTRIBUTES]):
                referral.save()
            # Clean up the record if no attribution attributes are set and it exists in the DB.
            elif referral.pk:
                referral.delete()
            # Otherwise we can ignore the instantiated but unsaved referral

    # Don't let attribution errors prevent users from creating baskets
    except:  # pylint: disable=broad-except, bare-except
        logger.exception('Error while attributing cookies to basket.')


@newrelic.agent.function_trace()
def _referral_from_basket_site(basket, site):
    try:
        # There should be only 1 referral instance for one basket.
        # Referral and basket has a one to one relationship
        referral = Referral.objects.get(basket=basket)
    except Referral.DoesNotExist:
        referral = Referral(basket=basket, site=site)
    return referral


@newrelic.agent.function_trace()
def _record_affiliate_basket_attribution(referral, request):
    """
      Attribute this user's basket to the referring affiliate, if applicable.
    """

    # TODO: update this line to use site configuration once config in production (2016-10-04)
    # affiliate_cookie_name = request.site.siteconfiguration.affiliate_cookie_name
    # affiliate_id = request.COOKIES.get(affiliate_cookie_name)

    affiliate_id = request.COOKIES.get(settings.AFFILIATE_COOKIE_KEY, "")
    referral.affiliate_id = affiliate_id


@newrelic.agent.function_trace()
def _record_utm_basket_attribution(referral, request):
    """
      Attribute this user's basket to UTM data, if applicable.
    """
    utm_cookie_name = request.site.siteconfiguration.utm_cookie_name
    utm_cookie = request.COOKIES.get(utm_cookie_name, "{}") if utm_cookie_name else "{}"
    utm = json.loads(utm_cookie)

    for attr_name in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']:
        setattr(referral, attr_name, utm.get(attr_name, ""))

    created_at_unixtime = utm.get('created_at')
    if created_at_unixtime:
        # We divide by 1000 here because the javascript timestamp generated is in milliseconds not seconds.
        # PYTHON: time.time()      => 1475590280.823698
        # JS: new Date().getTime() => 1475590280823
        created_at_datetime = datetime.datetime.fromtimestamp(int(created_at_unixtime) / float(1000), tz=pytz.UTC)
    else:
        created_at_datetime = None

    referral.utm_created_at = created_at_datetime


@newrelic.agent.function_trace()
def basket_add_organization_attribute(basket, request_data):
    """
    Adds the organization, and purchased_on_behalf attribute on basket, if organization value is provided
    in basket data. The purchased_on_behalf is not required if there is an organization value present.

    Arguments:
        basket(Basket): order basket
        request_data (dict): HttpRequest data

    """
    # Name of business client is being passed as "organization" from basket page
    business_client = request_data.get(ORGANIZATION_ATTRIBUTE_TYPE)
    purchaser = request_data.get(PURCHASER_BEHALF_ATTRIBUTE)

    if business_client:
        organization_attribute, __ = BasketAttributeType.objects.get_or_create(name=ORGANIZATION_ATTRIBUTE_TYPE)
        BasketAttribute.objects.get_or_create(
            basket=basket,
            attribute_type=organization_attribute,
            value_text=business_client.strip()
        )
        # Also add the 'purchaser' attribute to the carts of all business client purchases. This way we can track
        # how many people read/paid attention to the checkbox during purchases.
        purchaser_attribute, __ = BasketAttributeType.objects.get_or_create(name=PURCHASER_BEHALF_ATTRIBUTE)
        BasketAttribute.objects.get_or_create(
            basket=basket,
            attribute_type=purchaser_attribute,
            value_text=purchaser
        )


@newrelic.agent.function_trace()
def basket_add_payment_intent_id_attribute(basket, payment_intent_id):
    """
    Adds the Stripe payment_intent_id attribute on basket.

    Arguments:
        basket(Basket): order basket
        payment_intent_id (string): Payment Intent Identifier

    """

    payment_intent_id_attribute, __ = BasketAttributeType.objects.get_or_create(name=PAYMENT_INTENT_ID_ATTRIBUTE)
    # Do a get_or_create and update value_text after (instead of update_or_create)
    # to prevent a particularly slow full table scan that uses a LIKE
    basket_attribute, __ = BasketAttribute.objects.get_or_create(
        attribute_type=payment_intent_id_attribute,
        basket=basket,
    )
    basket_attribute.value_text = payment_intent_id.strip()
    basket_attribute.save()


@newrelic.agent.function_trace()
def basket_add_enterprise_catalog_attribute(basket, request_data):
    """
    Add enterprise catalog UUID attribute on basket, if the catalog UUID value
    is provided in the request.

    Arguments:
        basket(Basket): order basket
        request_data (dict): HttpRequest data

    """
    # Value of enterprise catalog UUID is being passed as `catalog` from
    # basket page
    enterprise_catalog_uuid = request_data.get('catalog') if request_data else None
    enterprise_catalog_attribute, __ = BasketAttributeType.objects.get_or_create(
        name=ENTERPRISE_CATALOG_ATTRIBUTE_TYPE
    )
    if enterprise_catalog_uuid:
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=enterprise_catalog_attribute,
            defaults={
                'value_text': enterprise_catalog_uuid.strip()
            }
        )
    else:
        # Remove the enterprise catalog attribute for future update in basket
        BasketAttribute.objects.filter(basket=basket, attribute_type=enterprise_catalog_attribute).delete()


@newrelic.agent.function_trace()
def _set_basket_bundle_status(bundle, basket):
    """
    Sets the basket's bundle status

    Note: This is a refactor of the existing code. Not sure
    what the intentions of the side effects are.

    Side effect:
        clears any vouchers if it's a bundle

    Args:
        bundle (str): The Bundle ID?
        basket (Basket): The basket to set the bundle attribute for

    Returns:

    """
    if bundle:
        BasketAttribute.objects.update_or_create(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE),
            defaults={'value_text': bundle}
        )
        basket.clear_vouchers()
    else:
        BasketAttribute.objects.filter(basket=basket, attribute_type__name=BUNDLE).delete()


@newrelic.agent.function_trace()
def validate_voucher(voucher, user, basket, request_site):
    """
    Validates if a voucher code can be used for user and basket.

    Args:
        voucher (Voucher) : Voucher to be validated
        user (User) : basket user
        basket (Basket) : Basket for which checking voucher
        request_site (Site) : Site on which voucher is being used

    Does the following checks
        1. Voucher is not expired.
        2. Voucher is active.
        3. Voucher is not already used.
        4. Voucher is not being used outside site scope.
        5. Voucher is valid for basket if its a bundle basket

    """
    if voucher.is_expired():
        message = _("Coupon code '{code}' has expired.").format(code=voucher.code)
        return False, message

    if not voucher.is_active():
        message = _("Coupon code '{code}' is not active.").format(code=voucher.code)
        return False, message

    is_available, msg = voucher.is_available_to_user(user)

    if not is_available:
        message = _("Coupon code '{code}' is not available. {msg}").format(code=voucher.code, msg=msg)
        return False, message

    # Do not allow coupons for one partner's site to be used on another partner's site
    voucher_partner = voucher.best_offer.partner
    if request_site and voucher_partner and request_site.siteconfiguration.partner != voucher_partner:
        message = _("Coupon code '{code}' is not valid for this basket.").format(code=voucher.code)
        return False, message

    # Do not allow single course run coupons used on bundles.
    bundle_attribute = BasketAttribute.objects.filter(
        basket=basket,
        attribute_type=BasketAttributeType.objects.get(name=BUNDLE)
    )
    is_bundle_purchase = len(bundle_attribute) > 0
    voucher_program_uuid = voucher.best_offer.condition.program_uuid
    is_voucher_valid_for_bundle = voucher_program_uuid or voucher.usage == Voucher.MULTI_USE

    if is_bundle_purchase and not is_voucher_valid_for_bundle:
        message = _("Coupon code '{code}' is not valid for this basket for a bundled purchase.").format(
            code=voucher.code)
        return False, message

    return True, ''


def apply_offers_on_basket(request, basket):
    """
    Applies offers on a basket.

    Adapted from `apply_offer_to_basket` in Oscar's `BasketMiddleware`, as
    trying to directly call the Middleware seems to cause issues with the new
    Django 1.11 style middleware.

    Args:
        request (Request): Request object
        basket (Basket): basket object on which the offers will be applied
    """
    if not basket.is_empty:
        Applicator().apply(basket, request.user, request)


@newrelic.agent.function_trace()
def apply_voucher_on_basket_and_check_discount(voucher, request, basket):
    """
    Applies voucher on a product.

    Args:
        voucher (Voucher): voucher to be applied
        basket (Basket): basket object on which voucher is going to be applied
        request (Request): Request object
    """
    # Note: some of this code was adapted from `apply_voucher_to_basket` in Oscar's `BasketAddView`.
    # See https://github.com/django-oscar/django-oscar/blob/1.5.1/src/oscar/apps/basket/views.py#L310-L356

    # Reset any site offers that are applied so that only one offer is active.
    basket.reset_offer_applications()
    basket.vouchers.add(voucher)
    voucher_addition.send(sender=None, basket=basket, voucher=voucher)

    Applicator().apply(basket, request.user, request)

    # Recalculate discounts to see if the voucher gives any
    discounts_after = basket.offer_applications

    # Look for discounts from this new voucher
    found_discount = False
    for discount in discounts_after:
        if discount['voucher'] and discount['voucher'] == voucher:
            found_discount = True
            break

    if found_discount:
        logger.info('Applied Voucher [%s] to basket [%s].', voucher.code, basket.id)
        msg = _("Coupon code '{code}' added to basket.").format(code=voucher.code)
        return True, msg

    msg = _('Basket does not qualify for coupon code {code}.').format(code=voucher.code)
    logger.info('Coupon Code [%s] is not valid for basket [%s]', voucher.code, basket.id)
    basket.clear_vouchers()
    return False, msg


def is_duplicate_seat_attempt(basket, product):
    """
    Checks basket for duplicate seat product

    Args:
        basket (Basket): basket object onto which we'll (potentially) add the new product
        product (Product): product to search for in the basket
    """

    product_type = product.get_product_class().name
    found_product_quantity = basket.product_quantity(product)

    return bool(product_type == 'Seat' and found_product_quantity)


def get_billing_address_from_payment_intent_data(payment_intent):
    """
    Take stripes response_data dict, instantiates a BillingAddress object
    and return it.
    """
    billing_details = payment_intent['payment_method']['billing_details']
    customer_address = billing_details['address']
    address = BillingAddress(
        first_name=billing_details['name'],  # Stripe only has a single name field
        last_name='',
        line1=customer_address['line1'],
        line2='' if not customer_address['line2'] else customer_address['line2'],  # line2 is optional
        line4=customer_address['city'],  # Oscar uses line4 for city
        postcode='' if not customer_address['postal_code'] else customer_address['postal_code'],  # postcode is optional
        state='' if not customer_address['state'] else customer_address['state'],  # state is optional
        country=Country.objects.get(iso_3166_1_a2__iexact=customer_address['country'])
    )
    return address


def set_email_preference_on_basket(request, basket):
    """
    Associate the user's email opt in preferences with the basket in
    order to opt them in later as part of fulfillment
    """
    BasketAttribute.objects.update_or_create(
        basket=basket,
        attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        defaults={'value_text': request.GET.get('email_opt_in') == 'true'},
    )

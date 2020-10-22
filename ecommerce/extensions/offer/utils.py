"""Offer Utility Methods. """


import logging
import string  # pylint: disable=W0402
from decimal import Decimal
from urllib.parse import urlencode

import bleach
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from ecommerce_worker.sailthru.v1.tasks import send_offer_assignment_email, send_offer_update_email
from oscar.core.loading import get_model

from ecommerce.core.url_utils import absolute_redirect
from ecommerce.extensions.checkout.utils import add_currency
from ecommerce.extensions.offer.constants import OFFER_ASSIGNED

logger = logging.getLogger(__name__)


def _remove_exponent_and_trailing_zeros(decimal):
    """
    Remove exponent and trailing zeros.

    Arguments:
        decimal (Decimal): Decimal number that needs to be modified

    Returns:
        decimal (Decimal): Modified decimal number without exponent and trailing zeros.
    """
    return decimal.quantize(Decimal(1)) if decimal == decimal.to_integral() else decimal.normalize()


def get_discount_percentage(discount_value, product_price):
    """
    Get discount percentage of discount value applied to a product price.
    Arguments:
        discount_value (float): Discount value
        product_price (float): Price of a product the discount is used on
    Returns:
        float: Discount percentage
    """
    return discount_value / product_price * 100 if product_price > 0 else 0.0


def get_discount_value(discount_percentage, product_price):
    """
    Get discount value of discount percentage applied to a product price.
    Arguments:
        discount_percentage (float): Discount percentage
        product_price (float): Price of a product the discount is used on
    Returns:
        float: Discount value
    """
    return discount_percentage * product_price / 100.0


def get_benefit_type(benefit):
    """ Returns type of benefit using 'type' or 'proxy_class' attributes of Benefit object"""
    _type = benefit.type

    if not _type:
        _type = getattr(benefit.proxy(), 'benefit_class_type', None)

    return _type


def get_quantized_benefit_value(benefit):
    """
    Returns the rounded value of the given benefit, without any decimal points.
    """
    value = getattr(benefit.proxy(), 'benefit_class_value', benefit.value)
    return _remove_exponent_and_trailing_zeros(Decimal(str(value)))


def format_benefit_value(benefit):
    """
    Format benefit value for display based on the benefit type

    Arguments:
        benefit (Benefit): Benefit to be displayed

    Returns:
        benefit_value (str): String value containing formatted benefit value and type.
    """
    Benefit = get_model('offer', 'Benefit')

    benefit_value = get_quantized_benefit_value(benefit)
    benefit_type = get_benefit_type(benefit)

    if benefit_type == Benefit.PERCENTAGE:
        benefit_value = _('{benefit_value}%'.format(benefit_value=benefit_value))
    else:
        converted_benefit = add_currency(Decimal(benefit.value))
        benefit_value = _('${benefit_value}'.format(benefit_value=converted_benefit))
    return benefit_value


def get_redirect_to_email_confirmation_if_required(request, offer, product):
    """
    Render the email confirmation template if email confirmation is
    required to redeem the offer.

    We require email confirmation via account activation before an offer
    can be redeemed if the site is configured to require account activation
    or if the offer is restricted for use to learners with a specific
    email domain. The learner needs to activate their account before we allow
    them to redeem email domain-restricted offers, otherwise anyone could create
    an account using an email address with a privileged domain and use the coupon
    code associated with the offer.

    Arguments:
        request (HttpRequest): The current HttpRequest.
        offer (ConditionalOffer): The offer to be redeemed.
        product (Product): The

    Returns:
        HttpResponse or None: An HttpResponse that redirects to the email confirmation view if required.
    """
    require_account_activation = request.site.siteconfiguration.require_account_activation or offer.email_domains
    if require_account_activation and not request.user.account_details(request).get('is_active'):
        response = absolute_redirect(request, 'offers:email_confirmation')
        course_id = product.course and product.course.id
        if course_id:
            response['Location'] += '?{params}'.format(params=urlencode({'course_id': course_id}))
        return response
    return None


def format_assigned_offer_email(greeting, closing, learner_email, code, redemptions_remaining, code_expiration_date):
    """
    Arguments:
        greeting (String): Email greeting (prefix)
        closing (String): Email closing (suffix)
        learner_email (String): Email of the customer who will receive the code.
        code (String): Code for the user.
        redemptions_remaining (Integer): Number of times the code can be redeemed.
        code_expiration_date(Datetime): Date till code is valid.


    Return the formatted email body for offer assignment.
    """
    email_template = settings.OFFER_ASSIGNMENT_EMAIL_TEMPLATE
    placeholder_dict = SafeDict(
        REDEMPTIONS_REMAINING=redemptions_remaining,
        USER_EMAIL=learner_email,
        CODE=code,
        EXPIRATION_DATE=code_expiration_date
    )
    return format_email(email_template, placeholder_dict, greeting, closing)


def send_assigned_offer_email(
        subject,
        greeting,
        closing,
        offer_assignment_id,
        learner_email,
        code,
        redemptions_remaining,
        code_expiration_date,
        base_enterprise_url=''):
    """
    Arguments:
        *subject*
            The email subject
        *email_greeting*
            The email greeting (prefix)
        *email_closing*
            The email closing (suffix)
        *offer_assignment_id*
            Primary key of the entry in the offer_assignment model.
        *learner_email*
            Email of the customer who will receive the code.
        *code*
            Code for the user.
        *redemptions_remaining*
            Number of times the code can be redeemed.
        *code_expiration_date*
            Date till code is valid.
    """
    email_body = format_assigned_offer_email(
        greeting,
        closing,
        learner_email,
        code,
        redemptions_remaining,
        code_expiration_date
    )
    send_offer_assignment_email.delay(learner_email, offer_assignment_id, subject, email_body, None,
                                      base_enterprise_url)


def send_revoked_offer_email(
        subject,
        greeting,
        closing,
        learner_email,
        code
):
    """
    Arguments:
        *subject*
            The email subject
        *email_greeting*
            The email greeting (prefix)
        *email_closing*
            The email closing (suffix)
        *learner_email*
            Email of the customer who will receive the code.
        *code*
            Code for the user.
    """
    email_template = settings.OFFER_REVOKE_EMAIL_TEMPLATE
    placeholder_dict = SafeDict(
        USER_EMAIL=learner_email,
        CODE=code,
    )
    email_body = format_email(email_template, placeholder_dict, greeting, closing)
    send_offer_update_email.delay(learner_email, subject, email_body)


def send_assigned_offer_reminder_email(
        subject,
        greeting,
        closing,
        learner_email,
        code,
        redeemed_offer_count,
        total_offer_count,
        code_expiration_date):
    """
    Arguments:
        *subject*
            The email subject
        *email_greeting*
            The email greeting (prefix)
        *email_closing*
            The email closing (suffix)
       *learner_email*
           Email of the customer who will receive the code.
       *code*
           Code for the user.
       *redeemed_offer_count*
           Number of times the code has been redeemed.
       *total_offer_count*
           Total number of offer assignments for this (code,email) pair
       *code_expiration_date*
           Date till code is valid.
    """
    email_template = settings.OFFER_REMINDER_EMAIL_TEMPLATE
    placeholder_dict = SafeDict(
        REDEEMED_OFFER_COUNT=redeemed_offer_count,
        TOTAL_OFFER_COUNT=total_offer_count,
        USER_EMAIL=learner_email,
        CODE=code,
        EXPIRATION_DATE=code_expiration_date
    )
    email_body = format_email(email_template, placeholder_dict, greeting, closing)
    send_offer_update_email.delay(learner_email, subject, email_body)


def format_email(template, placeholder_dict, greeting, closing):
    """
    Arguments:
        template (String): Email template body
        placeholder_dict (SafeDict): Safe dictionary of placeholders and their values
        greeting (String): Email greeting (prefix)
        closing (String): Email closing (suffix)

    Apply placeholders to the email template.

    Safely handle placeholders in the template without matching tokens (just emit the placeholders).

    Reference: https://stackoverflow.com/questions/17215400/python-format-string-unused-named-arguments
    """
    if greeting is None:
        greeting = ''
    if closing is None:
        closing = ''

    greeting = bleach.clean(greeting)
    closing = bleach.clean(closing)
    email_body = string.Formatter().vformat(template, SafeTuple(), placeholder_dict)
    # \n\n is being treated as single line except of two lines in HTML template,
    #  so separating them with &nbsp; tag to render them as expected.
    return (greeting + email_body + closing).replace('\n', '\n&nbsp;')


class SafeDict(dict):
    """
    Safely handle missing placeholder values.
    """
    def __missing__(self, key):
        return '{' + key + '}'


class SafeTuple(tuple):
    """
    Safely handle missing unnamed placeholder values in python3.
    """
    def __getitem__(self, value):
        return '{}'


def update_assignments_for_multi_use_per_customer(voucher):
    """
    Update `OfferAssignment` records for MULTI_USE_PER_CUSTOMER coupon type when max_uses changes for a coupon.
    """
    if voucher.usage == voucher.MULTI_USE_PER_CUSTOMER:
        OfferAssignment = get_model('offer', 'OfferAssignment')

        offer = voucher.enterprise_offer
        existing_offer_assignments = OfferAssignment.objects.filter(code=voucher.code, offer=offer).count()

        if existing_offer_assignments == 0:
            return

        if existing_offer_assignments < offer.max_global_applications:
            user_email = OfferAssignment.objects.filter(code=voucher.code, offer=offer).first().user_email
            offer_assignments_available = offer.max_global_applications - existing_offer_assignments
            assignments = [
                OfferAssignment(offer=offer, code=voucher.code, user_email=user_email, status=OFFER_ASSIGNED)
                for __ in range(offer_assignments_available)
            ]
            OfferAssignment.objects.bulk_create(assignments)

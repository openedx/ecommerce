"""Offer Utility Methods. """
import logging

from decimal import Decimal

from django.conf import settings
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from ecommerce_worker.sailthru.v1.tasks import send_offer_assignment_email, send_offer_update_email
from oscar.core.loading import get_model

from ecommerce.extensions.checkout.utils import add_currency

logger = logging.getLogger(__name__)
Benefit = get_model('offer', 'Benefit')


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


def format_benefit_value(benefit):
    """
    Format benefit value for display based on the benefit type

    Arguments:
        benefit (Benefit): Benefit to be displayed

    Returns:
        benefit_value (str): String value containing formatted benefit value and type.
    """
    benefit_value = _remove_exponent_and_trailing_zeros(Decimal(str(benefit.value)))
    benefit_type = benefit.type or getattr(benefit.proxy(), 'benefit_class_type', None)

    if benefit_type == Benefit.PERCENTAGE:
        benefit_value = _('{benefit_value}%'.format(benefit_value=benefit_value))
    else:
        converted_benefit = add_currency(Decimal(benefit.value))
        benefit_value = _('${benefit_value}'.format(benefit_value=converted_benefit))
    return benefit_value


def render_email_confirmation_if_required(request, offer, product):
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
        HttpResponse or None: An HttpResponse which renders the email confirmation template if required.
    """
    require_account_activation = request.site.siteconfiguration.require_account_activation or offer.email_domains
    if require_account_activation and not request.user.account_details(request).get('is_active'):
        return render(
            request,
            'edx/email_confirmation_required.html',
            {
                'course_name': product.course and product.course.name,
                'user_email': request.user and request.user.email,
            }
        )


def send_assigned_offer_email(
        template,
        offer_assignment_id,
        learner_email,
        code,
        redemptions_remaining,
        code_expiration_date):
    """
    Arguments:
        *template*
            The email template with placeholders that will receive the following tokens
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

    email_subject = settings.OFFER_ASSIGNMENT_EMAIL_DEFAULT_SUBJECT
    email_body = template.format(
        REDEMPTIONS_REMAINING=redemptions_remaining,
        USER_EMAIL=learner_email,
        CODE=code,
        EXPIRATION_DATE=code_expiration_date
    )
    send_offer_assignment_email.delay(learner_email, offer_assignment_id, email_subject, email_body)


def send_revoked_offer_email(template, learner_email, code):
    """
    Arguments:
        *template*
            The email template with placeholders that will receive the following tokens
        *learner_email*
            Email of the customer who will receive the code.
        *code*
            Code for the user.
    """

    email_subject = settings.OFFER_REVOKE_EMAIL_DEFAULT_SUBJECT

    email_body = template.format(
        USER_EMAIL=learner_email,
        CODE=code,
    )
    send_offer_update_email.delay(learner_email, email_subject, email_body)


def send_assigned_offer_reminder_email(
        template,
        learner_email,
        code,
        redeemed_offer_count,
        total_offer_count,
        code_expiration_date):
    """
    Arguments:
       *template*
           The email template with placeholders that will receive the following tokens
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

    email_subject = settings.OFFER_ASSIGNMENT_EMAIL_REMINDER_DEFAULT_SUBJECT
    email_body = template.format(
        REDEEMED_OFFER_COUNT=redeemed_offer_count,
        TOTAL_OFFER_COUNT=total_offer_count,
        USER_EMAIL=learner_email,
        CODE=code,
        EXPIRATION_DATE=code_expiration_date
    )
    send_offer_update_email.delay(learner_email, email_subject, email_body)

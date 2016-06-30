""" Checkout related views. """
from __future__ import unicode_literals

from decimal import Decimal
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, TemplateView
from oscar.apps.checkout.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.loading import get_class, get_model

from ecommerce.core.url_utils import get_ecommerce_url, get_lms_url
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
logger = logging.getLogger(__name__)


class FreeCheckoutView(EdxOrderPlacementMixin, RedirectView):
    """ View to handle free checkouts.

    Retrieves the user's basket and checks to see if the basket is free in which case
    the user is redirected to the receipt page. Otherwise the user is redirected back
    to the basket summary page.
    """

    permanent = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(FreeCheckoutView, self).dispatch(*args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):
        basket = Basket.get_basket(self.request.user, self.request.site)
        if not basket.is_empty:
            # Need to re-apply the voucher to the basket.
            Applicator().apply(basket, self.request.user, self.request)
            if basket.total_incl_tax != Decimal(0):
                raise BasketNotFreeError("Basket is not free.")

            order = self.place_free_order(basket)

            receipt_path = '{}?order_number={}'.format(settings.RECEIPT_PAGE_PATH, order.number)
            url = get_ecommerce_url(receipt_path)
        else:
            # If a user's basket is empty redirect the user to the basket summary
            # page which displays the appropriate message for empty baskets.
            url = reverse('basket:summary')
        return url


class CancelResponseView(RedirectView):
    """ Handles behaviour for the 'cancel' redirect. """
    permanent = False

    def get(self, request, *args, **kwargs):
        """ Retrieves the previously frozen basket from the kwargs and thaws it. """
        basket = get_object_or_404(Basket, id=kwargs['basket_id'],
                                   status=Basket.FROZEN)
        basket.thaw()
        logger.info('Payment for basket [%d] was cancelled. Transaction ID is [%s]. ',
                    request.GET.get('token', '<no token>'), basket.id)
        return super(CancelResponseView, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        """ Redirects back to the basket summary page. """
        return reverse('basket:summary')


class ReceiptResponseView(ThankYouView):
    """ Handles behavior needed to display an order receipt. """

    template_name = 'checkout/receipt.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ReceiptResponseView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReceiptResponseView, self).get_context_data(**kwargs)
        page_title = _('Receipt')
        is_payment_complete = True
        # NOTE: added PAYMENT_SUPPORT_EMAIL to ecommerce.yml
        payment_support_email = settings.PAYMENT_SUPPORT_EMAIL
        payment_support_link = '<a href=\"mailto:{email}\">{email}</a>'.format(email=payment_support_email)

        is_cybersource = all(k in self.request.POST for k in ('signed_field_names', 'decision', 'reason_code'))
        if is_cybersource and self.request.POST['decision'] != 'ACCEPT':
            # Cybersource may redirect users to this view if it couldn't recover
            # from an error while capturing payment info.
            is_payment_complete = False
            page_title = _('Payment Failed')
            error_summary = _("A system error occurred while processing your payment. You have not been charged.")
            error_text = _("Please wait a few minutes and then try again.")
            for_help_text = _("For help, contact {payment_support_link}.").format(payment_support_link=payment_support_link)
        else:
            # if anything goes wrong rendering the receipt, it indicates a problem fetching order data.
            error_summary = _("An error occurred while creating your receipt.")
            error_text = None  # nothing particularly helpful to say if this happens.
            for_help_text = _(
                "If your course does not appear on your dashboard, contact {payment_support_link}."
            ).format(payment_support_link=payment_support_link)

        context.update({
            'page_title': page_title,
            'is_payment_complete': is_payment_complete,
            'platform_name': settings.PLATFORM_NAME,
            # Need an LMS endpoint! 'verified': SoftwareSecurePhotoVerification.verification_valid_or_pending(request.user).exists(),
            'error_summary': error_summary,
            'error_text': error_text,
            'for_help_text': for_help_text,
            'payment_support_email': payment_support_email,
            'name': '{} {}'.format(self.request.user.first_name, self.request.user.last_name),
            'nav_hidden': True,
            'verify_link': get_lms_url('/verify_student/verify-now/'),
            'dashboard': get_lms_url('/dashboard'),
            'codes': [voucher.code for voucher in self.object.basket.vouchers.all()],
            # Need an LMS endpoint! 'is_request_in_themed_site': is_request_in_themed_site(),
            'course_key': self.object.lines.all()[0].product.course,
        })

        return context

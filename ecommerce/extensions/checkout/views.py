""" Checkout related views. """


import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, TemplateView
from oscar.apps.checkout.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.loading import get_class, get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, Timeout

from ecommerce.core.url_utils import (
    get_lms_course_about_url,
    get_lms_dashboard_url,
    get_lms_explore_courses_url,
    get_lms_program_dashboard_url
)
from ecommerce.enterprise.api import fetch_enterprise_learner_data
from ecommerce.enterprise.utils import find_active_enterprise_customer_user, has_enterprise_offer
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.utils import get_program_uuid

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
log = logging.getLogger(__name__)


class FreeCheckoutView(EdxOrderPlacementMixin, RedirectView):
    """ View to handle free checkouts.

    Retrieves the user's basket and checks to see if the basket is free in which case
    the user is redirected to the receipt page. Otherwise the user is redirected back
    to the basket summary page.
    """

    permanent = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):  # pylint: disable=arguments-differ
        return super(FreeCheckoutView, self).dispatch(*args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):
        request = self.request
        site = request.site
        basket = Basket.get_basket(request.user, site)

        if not basket.is_empty:
            # Need to re-apply the voucher to the basket.
            Applicator().apply(basket, request.user, request)
            if basket.total_incl_tax != Decimal(0):
                raise BasketNotFreeError(
                    'Basket [{}] is not free. User affected [{}]'.format(
                        basket.id,
                        basket.owner.id
                    )
                )

            order = self.place_free_order(basket)

            if has_enterprise_offer(basket):
                # Skip the receipt page and redirect to the LMS
                # if the order is free due to an Enterprise-related offer.
                program_uuid = get_program_uuid(order)
                if program_uuid:
                    url = get_lms_program_dashboard_url(program_uuid)
                else:
                    course_run_id = order.lines.all()[:1].get().product.course.id
                    url = get_lms_course_about_url(course_run_id)
            else:
                receipt_path = get_receipt_page_url(
                    self.request,
                    order_number=order.number,
                    site_configuration=order.site.siteconfiguration,
                    disable_back_button=True
                )
                url = site.siteconfiguration.build_lms_url(receipt_path)
        else:
            # If a user's basket is empty redirect the user to the basket summary
            # page which displays the appropriate message for empty baskets.
            url = reverse('basket:summary')
        return url


class CancelCheckoutView(TemplateView):
    """
    Displays a cancellation message when the customer cancels checkout on the
    payment processor page.
    """

    template_name = 'oscar/checkout/cancel_checkout.html'

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Request needs to be csrf_exempt to handle POST back from external payment processor.
        """
        return super(CancelCheckoutView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Allow POST responses from payment processors and just render the cancel page..
        """
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(CancelCheckoutView, self).get_context_data(**kwargs)
        context.update({
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email,
        })
        return context


class CheckoutErrorView(TemplateView):
    """ Displays an error page when checkout does not complete successfully. """

    template_name = 'oscar/checkout/error.html'

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Request needs to be csrf_exempt to handle POST back from external payment processor.
        """
        return super(CheckoutErrorView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Allow POST responses from payment processors and just render the error page.
        """
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(CheckoutErrorView, self).get_context_data(**kwargs)
        context.update({
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email,
        })
        return context


class ReceiptResponseView(ThankYouView):
    """ Handles behavior needed to display an order receipt. """
    template_name = 'edx/checkout/receipt.html'

    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """ Customers should only be able to view their receipts when logged in. """
        return super(ReceiptResponseView, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            response = super(ReceiptResponseView, self).get(request, *args, **kwargs)
        except Http404:
            self.template_name = 'edx/checkout/receipt_not_found.html'
            context = {
                'order_history_url': request.site.siteconfiguration.build_lms_url('account/settings'),
            }
            return self.render_to_response(context=context, status=404)
        enterprise_customer_user = self.get_metadata_for_enterprise_user(request)
        if enterprise_customer_user:
            enterprise_customer = enterprise_customer_user['enterprise_customer']
            learner_portal_url = self.get_enterprise_learner_portal_url(request, enterprise_customer)
            if learner_portal_url:
                self.add_message_if_enterprise_user(request, enterprise_customer, learner_portal_url)
                response.context_data['order_dashboard_url'] = learner_portal_url
            else:
                response.context_data['show_receipt_cta_links'] = False
        return response

    def get_context_data(self, **kwargs):  # pylint: disable=arguments-differ
        context = super(ReceiptResponseView, self).get_context_data(**kwargs)
        order = context[self.context_object_name]
        context['order_product_ids'] = ','.join(map(str, order.lines.values_list('product_id', flat=True)))
        has_enrollment_code_product = False
        if order.basket:
            has_enrollment_code_product = any(
                line.product.is_enrollment_code_product for line in order.basket.all_lines()
            )

        context.update({
            'payment_method': self.get_payment_method(order),
            'display_credit_messaging': self.order_contains_credit_seat(order),
        })
        context.update({
            'order_dashboard_url': self.get_order_dashboard_url(order),
            'explore_courses_url': get_lms_explore_courses_url(),
            'show_receipt_cta_links': True,
            'show_get_smarter_msg': self.order_contains_executive_education_2u_product(order),
            'has_enrollment_code_product': has_enrollment_code_product,
            'disable_back_button': self.request.GET.get('disable_back_button', 0),
        })
        if settings.AWIN_ADVERTISER_ID:
            context.update({
                'product_tracking': self.add_product_tracking(order),
            })
        return context

    def add_product_tracking(self, order):
        products_for_tracking = []
        for line in order.lines.all():
            if line.product.is_course_entitlement_product:
                product_id = line.product.attr.UUID
            else:
                product_id = line.product.course.id
            products_for_tracking.append("AW:P|{id}|{order_number}|{course_id}|{title}|{price}|"
                                         "{quantity}|{partner_sku}|DEFAULT\r\n"
                                         .format(id=settings.AWIN_ADVERTISER_ID, order_number=order.number,
                                                 course_id=product_id, title=line.title,
                                                 price=line.unit_price_incl_tax, quantity=line.quantity,
                                                 partner_sku=line.partner_sku)
                                         )
        return "".join(products_for_tracking)

    def get_object(self):
        kwargs = {
            'number': self.request.GET['order_number'],
            'site': self.request.site,
        }

        user = self.request.user
        if not user.is_staff:
            kwargs['user'] = user

        return get_object_or_404(Order, **kwargs)

    def get_payment_method(self, order):
        source = order.sources.first()
        if source:
            if source.card_type:
                return '{type} {number}'.format(
                    type=source.get_card_type_display(),
                    number=source.label
                )
            return source.source_type.name
        return None

    def order_contains_credit_seat(self, order):
        for line in order.lines.all():
            if getattr(line.product.attr, 'credit_provider', None):
                return True
        return False

    def order_contains_executive_education_2u_product(self, order):
        return any(line.product.is_executive_education_2u_product for line in order.lines.all())

    def get_order_dashboard_url(self, order):
        program_uuid = get_program_uuid(order)
        if program_uuid:
            order_dashboard_url = get_lms_program_dashboard_url(program_uuid)
        else:
            order_dashboard_url = get_lms_dashboard_url()
        return order_dashboard_url

    def get_metadata_for_enterprise_user(self, request):
        """
        Retrieves metadata about the authenticated user's linked enterprise customers. Returns the metadata
        for the `EnterpriseCustomerUser` record marked as active (i.e., there is only one active at a time) for
        the current Django session.
        """
        try:
            # If enterprise feature is enabled return all the enterprise_customer associated with user.
            learner_data = fetch_enterprise_learner_data(request.site, request.user)
        except (ReqConnectionError, KeyError, HTTPError, Timeout) as exc:
            log.info('[enterprise learner message] Exception while retrieving enterprise learner data for '
                     'User: %s, Exception: %s', request.user, exc)
            return None

        active_enterprise_customer_user = find_active_enterprise_customer_user(learner_data['results'])
        return active_enterprise_customer_user

    def get_enterprise_learner_portal_url(self, request, enterprise_customer):
        """
        Returns an enterprise learner portal URL string given a request and the metadata
        for an enterprise customer, or None if the specified enterprise customer is not
        configured for a learner portal URL.

        The enterprise customer must have a `slug`, and the `enable_learner_portal` and
        `enable_integrated_customer_learner_portal_search` fields turned on.

        Arguments:
            request: A request object
            enterprise_customer: Dictionary containing the following properties:
                - enable_learner_portal
                - enable_integrated_customer_learner_portal_search
                - slug

        """
        enable_learner_portal = enterprise_customer.get('enable_learner_portal')
        enable_integrated_customer_learner_portal_search = enterprise_customer.get(
            'enable_integrated_customer_learner_portal_search',
        )
        enterprise_learner_portal_slug = enterprise_customer.get('slug')

        if enable_learner_portal and enterprise_learner_portal_slug and enable_integrated_customer_learner_portal_search:  # pylint: disable=line-too-long
            learner_portal_url = '{scheme}://{hostname}/{slug}'.format(
                scheme=request.scheme,
                hostname=settings.ENTERPRISE_LEARNER_PORTAL_HOSTNAME,
                slug=enterprise_learner_portal_slug,
            )
            return learner_portal_url
        return None

    def add_message_if_enterprise_user(self, request, enterprise_customer, learner_portal_url):
        """
        Adds a info message alert informing the user of their enterprise learner portal dashboard. The message
        will only appear if the learner is linked to an enterprise customer with a valid learner portal URL.
        """
        if enterprise_customer and learner_portal_url:
            message = (
                'Your organization, {enterprise_customer_name}, has a dedicated page where '
                'you can see all of your sponsored courses. '
                'Go to <a href="{url}">your learner portal</a>.'
            ).format(
                enterprise_customer_name=enterprise_customer['name'],
                url=learner_portal_url
            )
            messages.add_message(request, messages.INFO, message, extra_tags='safe')

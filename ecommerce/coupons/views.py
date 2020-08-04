

import logging

import unicodecsv as csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView, View
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from oscar.core.loading import get_class, get_model
from rest_framework.views import APIView

from ecommerce.core.url_utils import absolute_redirect, get_ecommerce_url
from ecommerce.core.views import StaffOnlyMixin
from ecommerce.coupons.decorators import login_required_for_credit
from ecommerce.coupons.utils import is_voucher_applied
from ecommerce.enterprise.decorators import set_enterprise_cookie
from ecommerce.enterprise.exceptions import EnterpriseDoesNotExist
from ecommerce.enterprise.utils import (
    enterprise_customer_user_needs_consent,
    get_enterprise_course_consent_url,
    get_enterprise_customer_consent_failed_context_data,
    get_enterprise_customer_data_sharing_consent_token,
    get_enterprise_customer_from_voucher
)
from ecommerce.extensions.api import exceptions
from ecommerce.extensions.basket.utils import get_payment_microfrontend_or_basket_url, prepare_basket
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.offer.utils import get_redirect_to_email_confirmation_if_required
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.voucher.utils import get_voucher_and_products_from_code

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)
OrderLineVouchers = get_model('voucher', 'OrderLineVouchers')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


def voucher_is_valid(voucher, products, request):
    """
    Checks if the voucher is valid.

    Arguments:
        voucher (Voucher): The Voucher that is checked.
        products (list of Products): Products associated with the Voucher.
        request (Request): WSGI request.

    Returns:
        bool (bool): True if the voucher is valid, False otherwise.
        msg (str): Message in case the voucher is invalid.
        hide_error_message (bool): True if a support message should be hidden on the error page, False/None if not.
    """

    if voucher is None:
        return False, _('Coupon does not exist.'), False

    if not voucher.is_active():
        now = timezone.now()
        if voucher.start_datetime > now:
            return False, _('This coupon code is not yet valid.'), False
        if voucher.end_datetime < now:  # pragma: no cover
            return False, _('This coupon code has expired.'), True

    # We want to display the offer page to all users, including anonymous.
    if request.user.is_authenticated:
        avail, msg = voucher.is_available_to_user(request.user)
        if not avail:
            voucher_msg = msg.replace('voucher', 'coupon')
            return False, voucher_msg, False

    if len(products) == 1:
        purchase_info = request.strategy.fetch_for_product(products[0])
        if not purchase_info.availability.is_available_to_buy:
            return False, _('Product [{product}] not available for purchase.'.format(product=products[0])), False

    # If the voucher's number of applications exceeds it's limit.
    offer = voucher.best_offer
    if offer.get_max_applications(request.user) == 0:
        return False, _('This coupon code is no longer available.'), False

    return True, '', None


class CouponAppView(StaffOnlyMixin, TemplateView):
    template_name = 'coupons/coupon_app.html'

    def get_context_data(self, **kwargs):
        context = super(CouponAppView, self).get_context_data(**kwargs)
        context['admin'] = 'coupon'
        return context


class CouponOfferView(TemplateView):
    template_name = 'coupons/_offer_error.html'

    def get_context_data(self, **kwargs):
        code = self.request.GET.get('code', None)
        if code is None:
            return {'error': _('This coupon code is invalid.')}

        try:
            voucher, products = get_voucher_and_products_from_code(code=code)
        except Voucher.DoesNotExist:
            return {'error': _('Coupon does not exist.')}
        except exceptions.ProductNotFoundError:
            return {'error': _('The voucher is not applicable to your current basket.')}
        valid_voucher, msg, hide_error_message = voucher_is_valid(voucher, products, self.request)
        if not valid_voucher:
            return {'error': msg, 'hide_error_message': hide_error_message}

        context_data = super(CouponOfferView, self).get_context_data(**kwargs)
        context_data.update(get_enterprise_customer_consent_failed_context_data(self.request, voucher))

        if context_data and 'error' not in context_data:
            context_data.update({
                'offer_app_page_heading': _('Welcome to edX'),
                'offer_app_page_heading_message': _('Please choose from the courses selected by your '
                                                    'organization to start learning.')
            })
            self.template_name = 'coupons/offer.html'

        return context_data

    @method_decorator(login_required_for_credit)
    def get(self, request, *args, **kwargs):
        """Get method for coupon redemption page."""
        return super(CouponOfferView, self).get(request, *args, **kwargs)


class CouponRedeemView(EdxOrderPlacementMixin, APIView):
    permission_classes = (LoginRedirectIfUnauthenticated,)

    @method_decorator(set_enterprise_cookie)
    def get(self, request):  # pylint: disable=too-many-statements
        """
        Looks up the passed code and adds the matching product to a basket,
        then applies the voucher and if the basket total is FREE places the order and
        enrolls the user in the course.
        """
        template_name = 'coupons/_offer_error.html'
        code = request.GET.get('code')
        sku = request.GET.get('sku')
        failure_url = request.GET.get('failure_url')
        site_configuration = request.site.siteconfiguration

        if not code:
            return render(request, template_name, {'error': _('Code not provided.')})
        if not sku:
            return render(request, template_name, {'error': _('SKU not provided.')})

        try:
            voucher = Voucher.objects.get(code=code)
        except Voucher.DoesNotExist:
            msg = 'No voucher found with code {code}'.format(code=code)
            return render(request, template_name, {'error': _(msg)})

        try:
            product = StockRecord.objects.get(partner_sku=sku).product
        except StockRecord.DoesNotExist:
            return render(request, template_name, {'error': _('The product does not exist.')})

        valid_voucher, msg, hide_error_message = voucher_is_valid(voucher, [product], request)
        if not valid_voucher:
            logger.warning('[Code Redemption Failure] The voucher is not valid for this product. '
                           'User: %s, Product: %s, Code: %s, Message: %s',
                           request.user.username, product.id, voucher.code, msg)
            return render(request, template_name, {'error': msg, 'hide_error_message': hide_error_message})

        offer = voucher.best_offer
        if not offer.is_email_valid(request.user.email):
            logger.warning('[Code Redemption Failure] Unable to apply offer because the user\'s email '
                           'does not meet the domain requirements. '
                           'User: %s, Offer: %s, Code: %s', request.user.username, offer.id, voucher.code)
            return render(request, template_name, {'error': _('You are not eligible to use this coupon.')})

        email_confirmation_response = get_redirect_to_email_confirmation_if_required(request, offer, product)
        if email_confirmation_response:
            return email_confirmation_response

        try:
            enterprise_customer = get_enterprise_customer_from_voucher(request.site, voucher)
        except EnterpriseDoesNotExist as e:
            # If an EnterpriseException is caught while pulling the EnterpriseCustomer, that means there's no
            # corresponding EnterpriseCustomer in the Enterprise service (which should never happen).
            logger.exception(str(e))
            return render(
                request,
                template_name,
                {'error': _('Couldn\'t find a matching Enterprise Customer for this coupon.')}
            )

        if enterprise_customer and product.is_course_entitlement_product:
            return render(
                request,
                template_name,
                {
                    'error': _('This coupon is not valid for purchasing a program. Try using this on an individual '
                               'course in the program. If you need assistance, contact edX support.')
                }
            )

        if enterprise_customer is not None and enterprise_customer_user_needs_consent(
                request.site,
                enterprise_customer['id'],
                product.course.id,
                request.user.username,
        ):
            consent_token = get_enterprise_customer_data_sharing_consent_token(
                request.user.access_token,
                product.course.id,
                enterprise_customer['id']
            )
            received_consent_token = request.GET.get('consent_token')
            if received_consent_token:
                # If the consent token is set, then the user is returning from the consent view. Render out an error
                # if the computed token doesn't match the one received from the redirect URL.
                if received_consent_token != consent_token:
                    logger.warning('[Code Redemption Failure] Unable to complete code redemption because of '
                                   'invalid consent. User: %s, Offer: %s, Code: %s',
                                   request.user.username, offer.id, voucher.code)
                    return render(
                        request,
                        template_name,
                        {'error': _('Invalid data sharing consent token provided.')}
                    )
            else:
                # The user hasn't been redirected to the interstitial consent view to collect consent, so
                # redirect them now.
                redirect_url = get_enterprise_course_consent_url(
                    request.site,
                    code,
                    sku,
                    consent_token,
                    product.course.id,
                    enterprise_customer['id'],
                    failure_url=failure_url
                )
                return HttpResponseRedirect(redirect_url)

        try:
            basket = prepare_basket(request, [product], voucher)
        except AlreadyPlacedOrderException:
            msg = _('You have already purchased {course} seat.').format(course=product.course.name)
            return render(request, template_name, {'error': msg})

        if basket.total_excl_tax == 0:
            try:
                order = self.place_free_order(basket)
                return HttpResponseRedirect(
                    get_receipt_page_url(
                        site_configuration,
                        order.number,
                        disable_back_button=True,
                    ),
                )
            except:  # pylint: disable=bare-except
                logger.exception('Failed to create a free order for basket [%d]', basket.id)
                return absolute_redirect(self.request, 'checkout:error')

        if enterprise_customer:
            if is_voucher_applied(basket, voucher):
                message = _('A discount has been applied, courtesy of {enterprise_customer_name}.').format(
                    enterprise_customer_name=enterprise_customer.get('name')
                )
                messages.info(self.request, message)
            else:
                # Display a generic message to the user if a condition-specific
                # message has not already been added by an unsatified Condition class.
                if not messages.get_messages(self.request):
                    messages.warning(
                        self.request,
                        _('This coupon code is not valid for this course. Try a different course.'))
                self.request.basket.vouchers.remove(voucher)

        # The coupon_redeem_redirect query param is used to communicate to the Payment MFE that it may redirect
        # and should not display the payment form before making that determination.
        # TODO: It would be cleaner if the user could be redirected to their final destination up front.
        redirect_url = get_payment_microfrontend_or_basket_url(self.request) + "?coupon_redeem_redirect=1"
        return HttpResponseRedirect(redirect_url)


class EnrollmentCodeCsvView(View):
    """ Download enrollment code CSV file view. """

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):  # pylint: disable=arguments-differ
        return super(EnrollmentCodeCsvView, self).dispatch(*args, **kwargs)

    def get(self, request, number):
        """
        Creates a CSV for the order. The structure of the CSV looks like this:

           > Order Number:,EDX-100001

           > Seat in Demo with verified certificate (and ID verification)
           > Code,Redemption URL
           > J4HDI5OAUGCSUJJ3,ecommerce.server?code=J4HDI5OAUGCSUJJ3
           > OZCRR6WXLWGAFWZR,ecommerce.server?code=OZCRR6WXLWGAFWZR
           > 6KPYL6IO6Y3XL7SI,ecommerce.server?code=6KPYL6IO6Y3XL7SI
           > NPIJWIKNLRURYVU2,ecommerce.server?code=NPIJWIKNLRURYVU2
           > 6SZULKPZQYACAODC,ecommerce.server?code=6SZULKPZQYACAODC
           >

        Args:
            request (Request): The GET request
            number (str): Number of the order

        Returns:
            HttpResponse

        Raises:
            Http404: When an order number for a non-existing order is passed.
            PermissionDenied: When a user tries to download a CSV for an order that he did not make.

        """
        try:
            order = Order.objects.get(number=number)
        except Order.DoesNotExist:
            raise Http404('Order not found.')

        if request.user != order.user and not request.user.is_staff:
            raise PermissionDenied

        file_name = 'Enrollment code CSV order num {}'.format(order.number)
        file_name = '{filename}.csv'.format(filename=slugify(file_name))

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={filename}'.format(filename=file_name)

        redeem_url = get_ecommerce_url(reverse('coupons:offer'))
        voucher_field_names = ('Code', 'Redemption URL', 'Name Of Employee', 'Date Of Distribution', 'Employee Email')
        voucher_writer = csv.DictWriter(response, fieldnames=voucher_field_names)

        writer = csv.writer(response)
        writer.writerow(('Order Number:', order.number))
        writer.writerow([])

        order_line_vouchers = OrderLineVouchers.objects.filter(line__order=order)
        for order_line_voucher in order_line_vouchers:
            writer.writerow([order_line_voucher.line.product.title])
            voucher_writer.writeheader()

            for voucher in order_line_voucher.vouchers.all():
                voucher_writer.writerow({
                    voucher_field_names[0]: voucher.code,
                    voucher_field_names[1]: '{url}?code={code}'.format(url=redeem_url, code=voucher.code)
                })
            writer.writerow([])
        return response

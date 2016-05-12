from __future__ import unicode_literals
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView, View
from oscar.core.loading import get_class, get_model

from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import SlumberHttpBaseException

from ecommerce.core.url_utils import get_lms_url
from ecommerce.core.views import StaffOnlyMixin
from ecommerce.extensions.api import exceptions
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.offer.utils import format_benefit_value


Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
logger = logging.getLogger(__name__)
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


def get_voucher_from_code(code):
    """
    Returns a voucher and product for a given code.

    Arguments:
        code (str): The code of a coupon voucher.

    Returns:
        voucher (Voucher): The Voucher for the passed code.
        product (Product): The Product associated with the Voucher.

    Raises:
        Voucher.DoesNotExist: When no vouchers with provided code exist.
        ProductNotFoundError: When no products are associated with the voucher.
    """
    voucher = Voucher.objects.get(code=code)

    # Just get the first product.
    products = voucher.offers.all()[0].benefit.range.all_products()
    if products:
        product = products[0]
    else:
        raise exceptions.ProductNotFoundError()
    return voucher, product


def voucher_is_valid(voucher, product, request):
    """
    Checks if the voucher is valid.

    Arguments:
        voucher (Voucher): The Voucher that is checked.
        product (Product): Product associated with the Voucher.
        request (Request): WSGI request.

    Returns:
        bool (bool): True if the voucher is valid, False otherwise.
        msg (str): Message in case the voucher is invalid.
    """

    if voucher is None:
        return False, _('Coupon does not exist')

    if not voucher.is_active():
        now = timezone.now()
        if voucher.start_datetime > now:
            return False, _('This coupon code is not yet valid.')
        elif voucher.end_datetime < now:  # pragma: no cover
            return False, _('This coupon code has expired.')

    # We want to display the offer page to all users, including anonymous.
    if request.user.is_authenticated():
        avail, msg = voucher.is_available_to_user(request.user)
        if not avail:
            voucher_msg = msg.replace('voucher', 'coupon')
            return False, voucher_msg

    purchase_info = request.strategy.fetch_for_product(product)
    if not purchase_info.availability.is_available_to_buy:
        return False, _('Product [{product}] not available for purchase.'.format(product=product))

    # If the voucher's number of applications exceeds it's limit.
    offer = voucher.offers.first()
    if offer.get_max_applications(request.user) == 0:
        return False, _('This coupon code is no longer available.')

    return True, ''


class CouponAppView(StaffOnlyMixin, TemplateView):
    template_name = 'coupons/coupon_app.html'

    def get_context_data(self, **kwargs):
        context = super(CouponAppView, self).get_context_data(**kwargs)
        context['admin'] = 'coupon'
        return context


class CouponOfferView(TemplateView):
    template_name = 'coupons/offer.html'

    def get_context_data(self, **kwargs):
        context = super(CouponOfferView, self).get_context_data(**kwargs)
        code = self.request.GET.get('code', None)
        if code is not None:
            try:
                voucher, product = get_voucher_from_code(code=code)
            except Voucher.DoesNotExist:
                return {
                    'error': _('Coupon does not exist'),
                }
            except exceptions.ProductNotFoundError:
                return {
                    'error': _('The voucher is not applicable to your current basket.'),
                }
            valid_voucher, msg = voucher_is_valid(voucher, product, self.request)
            if valid_voucher:
                api = EdxRestApiClient(
                    get_lms_url('api/courses/v1/'),
                )
                try:
                    course = api.courses(product.course_id).get()
                except SlumberHttpBaseException as e:
                    logger.exception('Could not get course information. [%s]', e)
                    return {
                        'error': _('Could not get course information. [{error}]'.format(error=e)),
                    }
                course['image_url'] = get_lms_url(course['media']['course_image']['uri'])
                benefit = voucher.offers.first().benefit
                stock_record = benefit.range.catalog.stock_records.first()
                price = stock_record.price_excl_tax
                benefit_value = format_benefit_value(benefit)
                if benefit.type == 'Percentage':
                    new_price = price - (price * (benefit.value / 100))
                else:
                    new_price = price - benefit.value
                    if new_price < 0:
                        new_price = Decimal(0)

                context.update({
                    'analytics_data': prepare_analytics_data(
                        self.request.user,
                        self.request.site.siteconfiguration.segment_key,
                        product.course_id
                    ),
                    'benefit_value': benefit_value,
                    'course': course,
                    'code': code,
                    'is_discount_value_percentage': benefit.type == 'Percentage',
                    'is_enrollment_code': benefit.type == Benefit.PERCENTAGE and benefit.value == 100.00,
                    'discount_value': "%.2f" % (price - new_price),
                    'price': price,
                    'new_price': "%.2f" % new_price,
                    'verified': (product.attr.certificate_type == 'verified'),
                    'verification_deadline': product.course.verification_deadline,
                })
                return context
            return {
                'error': msg,
            }
        return {
            'error': _('This coupon code is invalid.'),
        }

    def get(self, request, *args, **kwargs):
        """Get method for coupon redemption page."""
        return super(CouponOfferView, self).get(request, *args, **kwargs)


class CouponRedeemView(EdxOrderPlacementMixin, View):

    @method_decorator(login_required)
    def get(self, request):
        """
        Looks up the passed code and adds the matching product to a basket,
        then applies the voucher and if the basket total is FREE places the order and
        enrolls the user in the course.
        """
        template_name = 'coupons/offer.html'
        code = request.GET.get('code', None)

        if not code:
            return render(request, template_name, {'error': _('Code not provided')})
        try:
            voucher, product = get_voucher_from_code(code=code)
        except Voucher.DoesNotExist:
            msg = 'No voucher found with code {code}'.format(code=code)
            return render(request, template_name, {'error': _(msg)})
        except exceptions.ProductNotFoundError:
            return render(request, template_name, {'error': _('The voucher is not applicable to your current basket.')})

        valid_voucher, msg = voucher_is_valid(voucher, product, request)
        if not valid_voucher:
            return render(request, template_name, {'error': msg})

        basket = prepare_basket(request, product, voucher)
        if basket.total_excl_tax == AC.FREE:
            self.place_free_order(basket)
        else:
            return HttpResponseRedirect(reverse('basket:summary'))

        return HttpResponseRedirect(get_lms_url(''))

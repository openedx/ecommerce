from __future__ import unicode_literals
from decimal import Decimal
import hashlib
import logging

from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from requests.exceptions import ConnectionError, Timeout
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from edx_rest_api_client.client import EdxRestApiClient
from slumber.exceptions import SlumberBaseException

from ecommerce.coupons.views import get_voucher_from_code
from ecommerce.extensions.api.data import get_lms_footer
from ecommerce.extensions.basket.utils import get_certificate_type_display_value, prepare_basket
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.settings import get_lms_url

Benefit = get_model('offer', 'Benefit')
logger = logging.getLogger(__name__)
StockRecord = get_model('partner', 'StockRecord')


class BasketSingleItemView(View):
    """
    View that adds a single product to a user's basket.
    An additional coupon code can be supplied so the offer is applied to the basket.
    """
    def get(self, request):
        partner = get_partner_for_site(request)

        sku = request.GET.get('sku', None)
        code = request.GET.get('code', None)

        if not sku:
            return HttpResponseBadRequest(_('No SKU provided.'))

        if code:
            voucher, __ = get_voucher_from_code(code=code)
        else:
            voucher = None

        try:
            product = StockRecord.objects.get(partner=partner, partner_sku=sku).product
        except StockRecord.DoesNotExist:
            return HttpResponseBadRequest(_('SKU [{sku}] does not exist.'.format(sku=sku)))

        purchase_info = request.strategy.fetch_for_product(product)
        if not purchase_info.availability.is_available_to_buy:
            return HttpResponseBadRequest(_('Product [{product}] not available to buy.'.format(product=product.title)))

        prepare_basket(request, product, voucher)
        return HttpResponseRedirect(reverse('basket:summary'), status=303)


class BasketSummaryView(BasketView):
    """
    Display basket contents and checkout/payment options.
    """
    def get_context_data(self, **kwargs):
        context = super(BasketSummaryView, self).get_context_data(**kwargs)
        lines = context.get('line_list', [])
        api = EdxRestApiClient(get_lms_url('api/courses/v1/'))
        for line in lines:
            course_id = line.product.course_id

            # Get each course type so we can display to the user at checkout.
            try:
                line.certificate_type = get_certificate_type_display_value(line.product.attr.certificate_type)
            except ValueError:
                line.certificate_type = None

            cache_key = 'courses_api_detail_{}'.format(course_id)
            cache_hash = hashlib.md5(cache_key).hexdigest()
            try:
                course = cache.get(cache_hash)
                if not course:
                    course = api.courses(course_id).get()
                    course['image_url'] = get_lms_url(course['media']['course_image']['uri'])
                    cache.set(cache_hash, course, settings.COURSES_API_CACHE_TIMEOUT)
                line.course = course
            except (ConnectionError, SlumberBaseException, Timeout):
                logger.exception('Failed to retrieve data from Course API for course [%s].', course_id)

            if line.has_discount:
                line.discount_percentage = line.discount_value / line.unit_price_incl_tax * Decimal(100)
            else:
                line.discount_percentage = 0
        context.update({
            'homepage_url': get_lms_url(''),
            'footer': get_lms_footer(),
            'lines': lines,
            'faq_url': get_lms_url('') + '/verified-certificate',
        })
        context.update(self.get_payment_processors())
        return context

    def get_payment_processors(self):
        """ Retrieve the list of active payment processors. """
        # TODO Retrieve this information from SiteConfiguration
        basket = self.request.basket
        user = self.request.user
        filter = lambda sequence: [item for item in sequence if item]
        processors = (
            get_processor_class(path)
            for path in settings.PAYMENT_PROCESSORS
        )
        enabled_processors = [
            processor() for processor in processors if processor.is_enabled()
        ]
        return {
            "payment_processors": [
                processor.render_payment_button(basket, user)
                for processor in enabled_processors
            ],
            "payment_processors_scripts": filter(
                processor.get_payment_page_script(basket, user)
                for processor in enabled_processors
            ),
            "payment_processors_remote_scripts": filter(
                processor.get_payment_remote_script(basket, user)
                for processor in enabled_processors
            )
        }




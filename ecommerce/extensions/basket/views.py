from __future__ import unicode_literals

import hashlib
import logging

from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _
from requests.exceptions import ConnectionError, Timeout
from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from edx_rest_api_client.client import EdxRestApiClient
from slumber.exceptions import SlumberBaseException

from ecommerce.core.url_utils import get_lms_url
from ecommerce.coupons.views import get_voucher_from_code
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.extensions.api.data import get_lms_footer
from ecommerce.extensions.basket.utils import get_certificate_type_display_value, prepare_basket
from ecommerce.extensions.offer.utils import format_benefit_value
from ecommerce.extensions.partner.shortcuts import get_partner_for_site

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
                benefit = self.request.basket.applied_offers().values()[0].benefit
                line.benefit_value = format_benefit_value(benefit)
            else:
                line.benefit_value = None

            context.update({
                'analytics_data': prepare_analytics_data(
                    self.request.user,
                    self.request.site.siteconfiguration.segment_key,
                    course_id
                ),
            })

        processors = self.request.site.siteconfiguration.get_payment_processors()
        context.update({
            'free_basket': context['order_total'].incl_tax == 0,
            'payment_processors': processors,
            'payment_processor_scripts': [
                processor().get_basket_page_script(self.request.basket, self.request.user)
                for processor in processors
            ],
            'homepage_url': get_lms_url(''),
            'footer': get_lms_footer(),
            'lines': lines,
        })
        return context

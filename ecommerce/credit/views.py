from urlparse import urljoin
import requests
import logging

from django.http import Http404
from django.views.generic import TemplateView
from django.conf import settings
import waffle

from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)


class Checkout(TemplateView):
    """Checkout page that describes the product the user is buying
    and displays the data of the institution offering credit.
    """
    template_name = 'edx/credit/checkout.html'
    CREDIT_MODE = 'credit'

    def get_context_data(self, **kwargs):
        context = super(Checkout, self).get_context_data(**kwargs)
        context['request'] = self.request
        context['user'] = self.request.user

        try:
            course = Course.objects.get(id=kwargs.get('course_id'))
        except Course.DoesNotExist:
            raise Http404

        context['course'] = course

        context['credit_seats'] = [
            seat for seat in course.seat_products if seat.attr.certificate_type == self.CREDIT_MODE
        ]

        if context['credit_seats']:
            provider_id = [seat.attr.credit_provider for seat in context['credit_seats']]
            context['providers'] = self.get_providers_from_lms(provider_id)

        return context

    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.switch_is_active('ENABLE_CREDIT_APP'):
            raise Http404
        return super(Checkout, self).get(request, args, **kwargs)

    def get_providers_from_lms(self, provider_id):
        """

        helper method for getting provider info from LMS with graceful
        error handling

        **Parameter**
            *provider_id: provider_id will be list containing provider ids

        **Returns**
            * get response from LMS as json containing list of providers and
            returns

        """

        provider_id = ",".join(provider_id)
        url = urljoin(settings.LMS_URL_ROOT, '/api/credit/v1/providers/?provider_id={}'.format(provider_id))
        try:
            response = requests.get(url)
        except requests.exceptions.RequestException as ex:
            logging.error(ex)
            return {}

        if response.status_code != 200:
            response.raise_for_status()

        return response.json()
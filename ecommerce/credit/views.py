from urlparse import urljoin

from django.http import Http404
from django.views.generic import TemplateView
from django.conf import settings
import requests
import waffle

from ecommerce.courses.models import Course


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
            provider_id = context['credit_seats'][0].attr.credit_provider
            url = urljoin(settings.LMS_URL_ROOT, '/api/credit/v1/provider/info/{}'.format(provider_id))
            response = requests.get(url)
            if response.status_code != 200:
                response.raise_for_status()
            context['provider_info'] = response.json()

        return context

    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.switch_is_active('ENABLE_CREDIT_APP'):
            raise Http404
        return super(Checkout, self).get(request, args, **kwargs)

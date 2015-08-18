from collections import OrderedDict
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
import waffle

from ecommerce.courses.models import Course
from ecommerce.extensions.payment.helpers import get_processor_class


class Checkout(TemplateView):
    """Checkout page that describes the product the user is buying
    and displays the data of the institution offering credit.
    """
    template_name = 'edx/credit/checkout.html'
    CREDIT_MODE = 'credit'

    def get_context_data(self, **kwargs):
        context = super(Checkout, self).get_context_data(**kwargs)

        try:
            course = Course.objects.get(id=kwargs.get('course_id'))
        except Course.DoesNotExist:
            raise Http404

        # Make button text for each processor which will be shown to user.
        processors_dict = OrderedDict()
        for path in settings.PAYMENT_PROCESSORS:
            processor = get_processor_class(path).NAME.lower()
            if processor == 'cybersource':
                processors_dict[processor] = 'Checkout'
            elif processor == 'paypal':
                processors_dict[processor] = 'Checkout with PayPal'
            else:
                processors_dict[processor] = 'Checkout with {}'.format(processor)

        credit_seats = [
            seat for seat in course.seat_products if getattr(seat.attr, 'certificate_type', '') == self.CREDIT_MODE
        ]
        provider_ids = None
        if credit_seats:
            provider_ids = ",".join([seat.attr.credit_provider for seat in credit_seats if seat.attr.credit_provider])

        context.update({
            'request': self.request,
            'user': self.request.user,
            'course': course,
            'payment_processors': processors_dict,
            'credit_seats': credit_seats,
            'lms_url_root': settings.LMS_URL_ROOT,
            'provider_ids': provider_ids,
            'analytics_data': json.dumps({
                'course': {
                    'courseId': course.id
                },
                'tracking': {
                    'segmentApplicationId': settings.SEGMENT_KEY
                },
                'user': {
                    'username': self.request.user.get_username(),
                    'name': self.request.user.get_full_name(),
                    'email': self.request.user.email
                }
            })
        })

        return context

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.switch_is_active('ENABLE_CREDIT_APP'):
            raise Http404
        return super(Checkout, self).get(request, args, **kwargs)

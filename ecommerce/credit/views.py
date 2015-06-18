from django.http import Http404
from django.views.generic import TemplateView
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

        return context

    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.switch_is_active('ENABLE_CREDIT_APP'):
            raise Http404
        return super(Checkout, self).get(request, args, **kwargs)

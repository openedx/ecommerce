from django.http import Http404
from django.views.generic import TemplateView

import waffle


class Checkout(TemplateView):
    """Checkout page that describes the product the user is buying
    and displays the data of the institution offering credit.
    """
    template_name = 'edx/credit/checkout.html'

    def get_context_data(self, **kwargs):
        context = super(Checkout, self).get_context_data(**kwargs)
        context['request'] = self.request
        context['user'] = self.request.user

        return context

    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.flag_is_active(request, 'ENABLE_CREDIT_APP'):
            raise Http404
        return super(Checkout, self).get(request, args, **kwargs)

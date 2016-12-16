from django.core.urlresolvers import reverse
from django.views.generic import TemplateView


class PaymentFailedView(TemplateView):
    template_name = 'checkout/payment_error.html'

    def get_context_data(self, **kwargs):
        context = super(PaymentFailedView, self).get_context_data(**kwargs)
        context.update({
            'basket_url': reverse('basket:summary'),
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email
        })
        return context

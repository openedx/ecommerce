from django.views.generic import TemplateView

from ecommerce.core.url_utils import get_lms_url


class PaymentFailedView(TemplateView):
    template_name = 'checkout/payment_error.html'

    def get_context_data(self, **kwargs):
        context = super(PaymentFailedView, self).get_context_data(**kwargs)
        context.update({
            'dashboard_url': get_lms_url(),
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email
        })
        return context


class SDNFailure(TemplateView):
    """ Display an error page when the SDN check fails at checkout. """
    template_name = 'checkout/sdn_failure.html'

    def get_context_data(self, **kwargs):
        context = super(SDNFailure, self).get_context_data(**kwargs)
        context['logout_url'] = self.request.site.siteconfiguration.build_lms_url('/logout')
        return context

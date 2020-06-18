# TODO: Refactor this to consolidate it with `ecommerce.programs.views`.


import logging

from django.contrib import messages
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.enterprise.forms import EnterpriseOfferForm
from ecommerce.enterprise.utils import get_enterprise_customer

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)


class EnterpriseOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(EnterpriseOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'enterprise_offers'
        return context

    def get_queryset(self):
        return super(EnterpriseOfferViewMixin, self).get_queryset().filter(
            partner=self.request.site.siteconfiguration.partner,
            condition__enterprise_customer_uuid__isnull=False,
            offer_type=ConditionalOffer.SITE
        )


class EnterpriseOfferProcessFormViewMixin(EnterpriseOfferViewMixin):
    form_class = EnterpriseOfferForm
    success_message = _('Enterprise offer updated!')

    def get_form_kwargs(self):
        kwargs = super(EnterpriseOfferProcessFormViewMixin, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(EnterpriseOfferProcessFormViewMixin, self).get_context_data(**kwargs)
        context.update({
            'editing': False,
        })
        return context

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, self.success_message)
        return reverse('enterprise:offers:edit', kwargs={'pk': self.object.pk})


class EnterpriseOfferCreateView(EnterpriseOfferProcessFormViewMixin, CreateView):
    initial = {
        'benefit_type': Benefit.PERCENTAGE,
    }
    success_message = _('Enterprise offer created!')
    template_name = 'enterprise/enterpriseoffer_form.html'


class EnterpriseOfferUpdateView(EnterpriseOfferProcessFormViewMixin, UpdateView):
    template_name = 'enterprise/enterpriseoffer_form.html'

    def get_context_data(self, **kwargs):
        context = super(EnterpriseOfferUpdateView, self).get_context_data(**kwargs)
        context.update({
            'editing': True,
            'enterprise_customer': get_enterprise_customer(
                self.request.site,
                self.object.condition.enterprise_customer_uuid
            )
        })
        return context


class EnterpriseOfferListView(EnterpriseOfferViewMixin, ListView):
    template_name = 'enterprise/enterpriseoffer_list.html'


class EnterpriseCouponAppView(StaffOnlyMixin, TemplateView):
    template_name = 'enterprise/enterprise_coupon_app.html'

    def get_context_data(self, **kwargs):
        context = super(EnterpriseCouponAppView, self).get_context_data(**kwargs)
        context['admin'] = 'enterprise_coupons'
        return context

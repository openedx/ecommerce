

import logging

from django.contrib import messages
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.programs.forms import ProgramOfferForm
from ecommerce.programs.utils import get_program

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)


class ProgramOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(ProgramOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'program_offers'
        return context

    def get_queryset(self):
        return super(ProgramOfferViewMixin, self).get_queryset().filter(
            partner=self.request.site.siteconfiguration.partner,
            condition__program_uuid__isnull=False,
            offer_type=ConditionalOffer.SITE
        )


class ProgramOfferProcessFormViewMixin(ProgramOfferViewMixin):
    form_class = ProgramOfferForm
    success_message = _('Program offer updated!')

    def get_form_kwargs(self):
        kwargs = super(ProgramOfferProcessFormViewMixin, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(ProgramOfferProcessFormViewMixin, self).get_context_data(**kwargs)
        context.update({
            'editing': False,
        })
        return context

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, self.success_message)
        return reverse('programs:offers:edit', kwargs={'pk': self.object.pk})


class ProgramOfferCreateView(ProgramOfferProcessFormViewMixin, CreateView):
    initial = {
        'benefit_type': Benefit.PERCENTAGE,
    }
    success_message = _('Program offer created!')
    template_name = 'programs/programoffer_form.html'


class ProgramOfferUpdateView(ProgramOfferProcessFormViewMixin, UpdateView):
    template_name = 'programs/programoffer_form.html'

    def get_context_data(self, **kwargs):
        context = super(ProgramOfferUpdateView, self).get_context_data(**kwargs)
        context.update({
            'editing': True,
            'program': get_program(self.object.condition.program_uuid,
                                   self.request.site.siteconfiguration),
        })
        return context


class ProgramOfferListView(ProgramOfferViewMixin, ListView):
    template_name = 'programs/programoffer_list.html'

    def get_context_data(self, **kwargs):
        context = super(ProgramOfferListView, self).get_context_data(**kwargs)

        # TODO: In the future, we should optimize our API calls, pulling the program data in as few calls as possible.
        offers = []
        for offer in context['object_list']:
            offer.program = get_program(offer.condition.program_uuid, self.request.site.siteconfiguration)
            offers.append(offer)

        return context

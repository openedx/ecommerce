# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import messages
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.journal.client import fetch_journal_bundle
from ecommerce.journal.forms import JournalOfferForm

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class JournalOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(JournalOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'journals'
        return context


class JournalProcessFormViewMixin(JournalOfferViewMixin):
    form_class = JournalOfferForm
    sucess_message = _('Journal Bundle offer updated!')

    def get_form_kwargs(self):
        kwargs = super(JournalProcessFormViewMixin, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(JournalOfferViewMixin, self).get_context_data(**kwargs)     # pylint: disable=bad-super-call
        context.update({
            'editing': False
        })
        return context

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, self.sucess_message)
        return reverse('journal:offers:edit', kwargs={'pk': self.object.pk})


class JournalOfferCreateView(JournalProcessFormViewMixin, CreateView):
    initial = {
        'benefit_type': Benefit.PERCENTAGE
    }
    success_message = _('Journal Bundle offer created!')
    template_name = 'journal/journaloffer_form.html'


class JournalOfferUpdateView(JournalProcessFormViewMixin, UpdateView):
    template_name = 'journal/journaloffer_form.html'

    def get_context_data(self, **kwargs):
        context = super(JournalOfferUpdateView, self).get_context_data(**kwargs)
        context.update({
            'editing': True,
            'journal_bundle': fetch_journal_bundle(
                site=self.request.site,
                journal_bundle_uuid=self.object.condition.journal_bundle_uuid
            )
        })
        return context


class JournalOfferListView(JournalOfferViewMixin, ListView):
    template_name = 'journal/journaloffer_list.html'

    def get_context_data(self, **kwargs):
        context = super(JournalOfferListView, self).get_context_data(**kwargs)

        offers = []
        # context['object_list'] returns all conditional offers (including enterprise and program)
        # we only want to pass journal bundle offers to the context, so ignore all offers that do not
        # have a journal bundle uuid
        for offer in context['object_list']:
            if offer.condition.journal_bundle_uuid:
                offer.journal_bundle = fetch_journal_bundle(
                    site=self.request.site,
                    journal_bundle_uuid=offer.condition.journal_bundle_uuid
                )
                offers.append(offer)

        context['offers'] = offers
        return context

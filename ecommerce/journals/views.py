# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import messages
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.journals.client import fetch_journal_bundle
from ecommerce.journals.forms import JournalBundleOfferForm

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class JournalBundleOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(JournalBundleOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'journals'
        return context

    def get_queryset(self):
        return super(JournalBundleOfferViewMixin, self).get_queryset().filter(
            partner=self.request.site.siteconfiguration.partner,
            condition__journal_bundle_uuid__isnull=False,
            offer_type=ConditionalOffer.SITE
        )


class JournalBundleProcessFormViewMixin(JournalBundleOfferViewMixin):
    form_class = JournalBundleOfferForm
    sucess_message = _('Journal Bundle offer updated!')

    def get_form_kwargs(self):
        kwargs = super(JournalBundleProcessFormViewMixin, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(JournalBundleOfferViewMixin, self).get_context_data(**kwargs)     # pylint: disable=bad-super-call
        context.update({
            'editing': False
        })
        return context

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, self.sucess_message)
        return reverse('journals:offers:edit', kwargs={'pk': self.object.pk})


class JournalBundleOfferCreateView(JournalBundleProcessFormViewMixin, CreateView):
    initial = {
        'benefit_type': Benefit.PERCENTAGE
    }
    success_message = _('Journal Bundle offer created!')
    template_name = 'journals/journalbundleoffer_form.html'


class JournalBundleOfferUpdateView(JournalBundleProcessFormViewMixin, UpdateView):
    template_name = 'journals/journalbundleoffer_form.html'

    def get_context_data(self, **kwargs):
        context = super(JournalBundleOfferUpdateView, self).get_context_data(**kwargs)
        context.update({
            'editing': True,
            'journal_bundle': fetch_journal_bundle(
                site=self.request.site,
                journal_bundle_uuid=self.object.condition.journal_bundle_uuid
            )
        })
        return context


class JournalBundleOfferListView(JournalBundleOfferViewMixin, ListView):
    template_name = 'journals/journalbundleoffer_list.html'

    def get_context_data(self, **kwargs):
        context = super(JournalBundleOfferListView, self).get_context_data(**kwargs)

        offers = []
        for offer in context['object_list']:
            offer.journal_bundle = fetch_journal_bundle(
                site=self.request.site,
                journal_bundle_uuid=offer.condition.journal_bundle_uuid
            )
            offers.append(offer)

        context['offers'] = offers
        return context

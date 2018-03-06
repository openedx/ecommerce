from django.contrib import messages
from django.urls import reverse
from django.views.generic import ListView, CreateView, UpdateView
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.digital_books.utils import get_digital_book_bundle
from ecommerce.digital_books.forms import DigitalBookOfferForm

import logging
logger = logging.getLogger(__name__)

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class DigitalBookOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'digital_books'
        return context


class DigitalBookProcessFormViewMixin(DigitalBookOfferViewMixin):
    form_class = DigitalBookOfferForm
    success_message = _('Digital Book offer updated!')

    def get_form_kwargs(self):
        kwargs = super(DigitalBookProcessFormViewMixin, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferViewMixin, self).get_context_data(**kwargs)
        context.update({
            'editing': False,
        })
        return context

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, self.success_message)
        #TODO: send to digital book edit page
        # return reverse('digital-book:offers:edit', kwargs={'pk': self.object.pk})
        return reverse('digital-books:offers:list')


class DigitalBookOfferCreateView(DigitalBookProcessFormViewMixin, CreateView):
    initial = {
        'benefit_type': Benefit.PERCENTAGE
    }
    success_message = _('Digital Book offer created!')
    template_name = 'digital_books/digitalbookoffer_form.html'


class DigitalBookOfferListView(DigitalBookOfferViewMixin, ListView):
    template_name = 'digital_books/digitalbookoffer_list.html'

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferListView, self).get_context_data(**kwargs)

        # TODO: generate list of digital book offers
        offers = []
        for offer in context['object_list']:
            offer.digital_book_bundle = get_digital_book_bundle(offer.condition.digital_book_bundle_uuid, self.request.site.siteconfiguration)
            offers.append(offer)

        return context

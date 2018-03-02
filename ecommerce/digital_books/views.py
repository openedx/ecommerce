from django.views.generic import ListView
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin

ConditionalOffer = get_model('offer', 'ConditionalOffer')

class DigitalBookOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'digital_books'

class DigitalBookOfferListView(DigitalBookOfferViewMixin, ListView):
    template_name = 'digital_books/digitalbookoffer_list.html'

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferListView, self).get_context_data(**kwargs)

        # TODO: generate list of digital book offers
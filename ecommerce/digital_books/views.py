from django.views.generic import ListView, CreateView
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.digital_books.forms import DigitalBookOfferForm

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class DigitalBookOfferViewMixin(StaffOnlyMixin):
    model = ConditionalOffer

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferViewMixin, self).get_context_data(**kwargs)
        context['admin'] = 'digital_books'


class DigitalBookProcessFormViewMixin(DigitalBookOfferViewMixin):
    form_class = DigitalBookOfferForm
    success_message = _('Digital Book offer updated!')

    def get_from_kwargs(self):
        kwargs = super(DigitalBookProcessFormViewMixin,self).get_form_kwargs()
        kwargs.update({
            'request': self.request,
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferViewMixin, self).get_context_data(**kwargs)
        context.update({
            'editing': False,
        })
        return context

    #TODO: get_sueccess_url

class DigitalBookOfferCreateView(DigitalBookProcessFormViewMixin, CreateView):
    initial = {
        'benefit_type': Benefit.PERCENTAGE
    }
    success_message = _('Digital Book offer created!')
    #TODO: replace with digital book offer form
    template_name = 'digital_books/digitalbookoffer_form.html'


class DigitalBookOfferListView(DigitalBookOfferViewMixin, ListView):
    template_name = 'digital_books/digitalbookoffer_list.html'

    def get_context_data(self, **kwargs):
        context = super(DigitalBookOfferListView, self).get_context_data(**kwargs)

        # TODO: generate list of digital book offers
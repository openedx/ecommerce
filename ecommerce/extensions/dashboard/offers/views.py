

import json

from django.contrib.sites.models import Site
from django.core.serializers.json import DjangoJSONEncoder
from oscar.apps.dashboard.offers.views import OfferMetaDataView as CoreOfferMetaDataView
from oscar.apps.dashboard.offers.views import OfferRestrictionsView as CoreOfferRestrictionsView


class OfferMetaDataView(CoreOfferMetaDataView):

    def _store_form_kwargs(self, form):
        session_data = self.request.session.setdefault(self.wizard_name, {})

        # Adjust kwargs to save site_id rather than site which can't be serialized in the session
        form_data = form.cleaned_data.copy()
        site = form_data['site']
        form_data['site_id'] = site.id
        del form_data['site']
        form_kwargs = {'data': form_data}
        json_data = json.dumps(form_kwargs, cls=DjangoJSONEncoder)
        session_data[self._key()] = json_data
        self.request.session.save()

    def _fetch_form_kwargs(self, step_name=None):

        if not step_name:
            step_name = self.step_name
        session_data = self.request.session.setdefault(self.wizard_name, {})
        json_data = session_data.get(self._key(step_name), None)
        if json_data:
            form_kwargs = json.loads(json_data)
            form_kwargs['data']['site'] = Site.objects.get(pk=form_kwargs['data']['site_id'])
            del form_kwargs['data']['site_id']
            return form_kwargs

        return {}


class OfferRestrictionsView(CoreOfferRestrictionsView):

    def form_valid(self, form):
        offer = form.save(commit=False)

        # Make sure to save offer.site from the session_offer
        session_offer = self._fetch_session_offer()
        offer.partner = session_offer.site.siteconfiguration.partner
        return self.save_offer(offer)

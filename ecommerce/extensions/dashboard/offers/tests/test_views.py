

import json

from django.urls import reverse
from oscar.core.loading import get_model
from oscar.test.factories import RangeFactory

from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class OfferWizardTests(TestCase):
    def test_site(self):
        """ Verify the site is stored in the session. """
        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)
        site_configuration = SiteConfigurationFactory()
        site = site_configuration.site

        self.assertEqual(ConditionalOffer.objects.exclude(name='dynamic_conditional_offer').count(), 0)

        # Start creating the offer by defining by setting the name and site
        metadata = {
            'name': 'Test Offer',
            'description': 'Blah!',
            'site': site.id,
        }
        metadata_url = reverse('dashboard:offer-metadata')
        response = self.client.post(metadata_url, metadata)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard:offer-benefit'))

        # Ensure the Site ID is stored in the session
        actual = json.loads(self.client.session['offer_wizard']['metadata'])['data']['site_id']
        self.assertEqual(actual, site.id)

        # Set the offer benfit data
        offer_range = RangeFactory()
        data = {
            'range': offer_range.id,
            'type': Benefit.PERCENTAGE,
            'value': 100
        }
        response = self.client.post(response['Location'], data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard:offer-condition'))

        # Set the conditions on the offer
        restrictions_url = reverse('dashboard:offer-restrictions')
        data = {
            'range': offer_range.id,
            'type': Condition.COUNT,
            'value': 1
        }
        response = self.client.post(response['Location'], data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], restrictions_url)

        # Reload the first page to exercise _fetch_form_kwargs, which should pull the site from the session
        response = self.client.get(metadata_url)
        self.assertEqual(response.status_code, 200)

        # Finish saving the offer by setting the restrictions
        data = {
            'priority': 0,
            'exclusive': True
        }
        response = self.client.post(restrictions_url, data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(ConditionalOffer.objects.exclude(name='dynamic_conditional_offer').count(), 1)
        offer = ConditionalOffer.objects.exclude(name='dynamic_conditional_offer').first()
        self.assertEqual(response['Location'], reverse('dashboard:offer-detail', kwargs={'pk': offer.pk}))

        # Ensure the offer is associated to the partner set in the first step of the wizard
        self.assertEqual(offer.partner, site_configuration.partner)

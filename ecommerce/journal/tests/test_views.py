import uuid

import mock
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase, TieredCacheMixin, ViewTestMixin

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


def _get_mocked_endpoint():
    journal_bundle = mock.Mock()
    journal_bundle.uuid = str(uuid.uuid4())
    journal_bundle.title = "mocked_title"
    return journal_bundle


class JournalOfferListViewTests(ViewTestMixin, TestCase):

    def setUp(self):
        super(JournalOfferListViewTests, self).setUp()
        self.path = reverse('journal:offers:list')

    @mock.patch('ecommerce.journal.views.fetch_journal_bundle')
    def test_get(self, mock_journal_endpoint):
        """ Test the "GET" endpoint with offers and assert the rendered template """
        mock_journal_endpoint.return_value = _get_mocked_endpoint()

        journal_offers = factories.JournalOfferFactory.create_batch(3)

        response = self.assert_get_response_status(200)
        self.assertContains(response, "mocked_title")
        self.assertContains(response, "Journal Bundle Offers")
        self.assertEqual(list(response.context['object_list']), journal_offers)

    def test_get_without_offers(self):
        """ Test the "GET" endpoint without any offer """

        response = self.assert_get_response_status(200)
        self.assertContains(response, "Journal Bundle Offers")
        self.assertEqual(list(response.context['object_list']), [])


@mock.patch('ecommerce.journal.views.fetch_journal_bundle')
@mock.patch('ecommerce.journal.forms.fetch_journal_bundle')
class JournalOfferUpdateViewTests(TestCase, TieredCacheMixin):

    def setUp(self):
        super(JournalOfferUpdateViewTests, self).setUp()
        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)
        self.journal_offer = factories.JournalOfferFactory(site=self.site)
        self.path = reverse('journal:offers:edit', kwargs={'pk': self.journal_offer.pk})

    def test_get(self, mock_discovery_call_post, mock_discovery_call_update):
        """ The context should contain the journal offer. """

        mock_discovery_call_post.return_value = {"title": "test-journal"}
        mock_discovery_call_update.return_value = _get_mocked_endpoint()

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['object'], self.journal_offer)

    def test_post(self, mock_discovery_call_post, mock_discovery_call_update):
        """ The journal offer should be updated. """

        mock_discovery_call_post.return_value = {"title": "test-journal"}
        mock_discovery_call_update.return_value = _get_mocked_endpoint()
        expected_benefit_value = 55
        data = {
            'journal_bundle_uuid': self.journal_offer.condition.journal_bundle_uuid,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': expected_benefit_value,
        }
        response = self.client.post(self.path, data, follow=False)
        self.assertRedirects(response, self.path)

        updated_journal_offer = ConditionalOffer.objects.get()
        self.assertEqual(updated_journal_offer.benefit.value, expected_benefit_value)

    def test_post_with_invalid_data(self, mock_discovery_call_post, mock_discovery_call_update):
        """ The journal offer should not be updated with invalid data. """
        mock_discovery_call_post.return_value = {"title": "test-journal"}
        mock_discovery_call_update.return_value = _get_mocked_endpoint()
        expected_benefit_value = 20

        data = {
            "dummy-key": "dummy-value",
            "benefit_type": Benefit.PERCENTAGE,
            "benefit_value": expected_benefit_value,
        }
        self.client.post(self.path, data, follow=False)
        self.assertNotEqual(ConditionalOffer.objects.get().benefit.value, expected_benefit_value)


class JournalOfferCreateViewTests(ViewTestMixin, TestCase):

    path = reverse('journal:offers:new')

    @mock.patch('ecommerce.journal.views.fetch_journal_bundle')
    @mock.patch('ecommerce.journal.forms.fetch_journal_bundle')
    def test_post(self, mock_discovery_call_post, mock_discovery_call_update):
        """ A new journal offer should be created. """

        mock_discovery_call_post.return_value = {"title": "test-journal"}
        mock_discovery_call_update.return_value = _get_mocked_endpoint()
        expected_journal_bundle_uuid = uuid.uuid4()
        expected_benefit_value = 10
        data = {
            'journal_bundle_uuid': expected_journal_bundle_uuid,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': expected_benefit_value,
        }
        response = self.client.post(self.path, data)
        journal_offer = ConditionalOffer.objects.get()
        self.assertIsNone(journal_offer.start_datetime)
        self.assertIsNone(journal_offer.end_datetime)
        self.assertEqual(journal_offer.benefit.value, expected_benefit_value)
        self.assertEqual(journal_offer.condition.journal_bundle_uuid, expected_journal_bundle_uuid)
        self.assertRedirects(response, reverse('journal:offers:edit', kwargs={'pk': journal_offer.pk}))

    def test_post_with_invalid_data(self):
        """ A new journal offer should not be created with invalid data. """

        condition_offers_count = ConditionalOffer.objects.count()
        data = {
            "dummy-key": "dummy-value",
            "benefit_type": Benefit.PERCENTAGE
        }
        self.client.post(self.path, data)
        # ConditionOffer count remains same.
        self.assertEqual(ConditionalOffer.objects.count(), condition_offers_count)

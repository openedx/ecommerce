

import uuid

import httpretty
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.extensions.test import factories
from ecommerce.programs.benefits import PercentageDiscountBenefitWithoutRange
from ecommerce.programs.custom import class_path
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.testcases import TestCase, ViewTestMixin

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class ProgramOfferListViewTests(ProgramTestMixin, ViewTestMixin, TestCase):
    path = reverse('programs:offers:list')

    def setUp(self):
        super(ProgramOfferListViewTests, self).setUp()

        httpretty.enable()
        self.mock_access_token_response()

    def tearDown(self):
        super(ProgramOfferListViewTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def test_get(self):
        """ The context should contain a list of program offers. """

        # These should be ignored since their associated Condition objects do NOT have a program UUID.
        factories.ConditionalOfferFactory.create_batch(3)

        program_offers = factories.ProgramOfferFactory.create_batch(4, partner=self.partner)

        for offer in program_offers:
            self.mock_program_detail_endpoint(offer.condition.program_uuid, self.site_configuration.discovery_api_url)

        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), program_offers)

        # The page should load even if the Programs API is inaccessible
        httpretty.disable()
        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), program_offers)

    def test_get_queryset(self):
        """ Should return only Conditional Offers with Site offer type. """

        # Conditional Offer should contain a condition with program uuid set in order to be returned
        site_conditional_offer = factories.ProgramOfferFactory(partner=self.partner)

        # Conditional Offer with null Partner or non-matching Partner should not be returned
        null_partner_offer = factories.ProgramOfferFactory()
        different_partner_offer = factories.ProgramOfferFactory(partner=factories.SiteConfigurationFactory().partner)
        program_offers = [
            site_conditional_offer,
            factories.ProgramOfferFactory(offer_type=ConditionalOffer.VOUCHER),
            factories.ConditionalOfferFactory(offer_type=ConditionalOffer.SITE),
            null_partner_offer,
            different_partner_offer
        ]

        for offer in program_offers:
            self.mock_program_detail_endpoint(offer.condition.program_uuid, self.site_configuration.discovery_api_url)

        response = self.client.get(self.path)
        self.assertEqual(list(response.context['object_list']), [site_conditional_offer])


class ProgramOfferUpdateViewTests(ProgramTestMixin, ViewTestMixin, TestCase):
    def setUp(self):
        super(ProgramOfferUpdateViewTests, self).setUp()
        self.program_offer = factories.ProgramOfferFactory(partner=self.partner)
        self.path = reverse('programs:offers:edit', kwargs={'pk': self.program_offer.pk})

        # NOTE: We activate httpretty here so that we don't have to decorate every test method.
        httpretty.enable()
        self.mock_program_detail_endpoint(
            self.program_offer.condition.program_uuid, self.site_configuration.discovery_api_url
        )

    def tearDown(self):
        super(ProgramOfferUpdateViewTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def test_get(self):
        """ The context should contain the program offer. """
        response = self.assert_get_response_status(200)
        self.assertEqual(response.context['object'], self.program_offer)

        # The page should load even if the Programs API is inaccessible
        httpretty.disable()
        response = self.assert_get_response_status(200)
        self.assertEqual(response.context['object'], self.program_offer)

    def test_post(self):
        """ The program offer should be updated. """
        data = {
            'program_uuid': self.program_offer.condition.program_uuid,
            'benefit_type': self.program_offer.benefit.proxy().benefit_class_type,
            'benefit_value': self.program_offer.benefit.value,
        }
        response = self.client.post(self.path, data, follow=False)
        self.assertRedirects(response, self.path)


@httpretty.activate
class ProgramOfferCreateViewTests(ProgramTestMixin, ViewTestMixin, TestCase):
    path = reverse('programs:offers:new')

    def test_post(self):
        """ A new program offer should be created. """
        expected_uuid = uuid.uuid4()
        self.mock_program_detail_endpoint(expected_uuid, self.site_configuration.discovery_api_url)
        expected_benefit_value = 10
        data = {
            'program_uuid': expected_uuid,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': expected_benefit_value,
        }
        existing_offer_ids = list(ConditionalOffer.objects.all().values_list('id', flat=True))
        response = self.client.post(self.path, data, follow=False)
        conditional_offers = ConditionalOffer.objects.exclude(id__in=existing_offer_ids)
        program_offer = conditional_offers.first()
        self.assertEqual(conditional_offers.count(), 1)

        self.assertRedirects(response, reverse('programs:offers:edit', kwargs={'pk': program_offer.pk}))
        self.assertIsNone(program_offer.start_datetime)
        self.assertIsNone(program_offer.end_datetime)
        self.assertEqual(program_offer.condition.program_uuid, expected_uuid)
        self.assertEqual(program_offer.benefit.type, '')
        self.assertEqual(program_offer.benefit.value, expected_benefit_value)
        self.assertEqual(program_offer.benefit.proxy_class, class_path(PercentageDiscountBenefitWithoutRange))

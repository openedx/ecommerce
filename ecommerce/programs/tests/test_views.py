import uuid

import httpretty
from django.conf import settings
from django.core.urlresolvers import reverse
from oscar.core.loading import get_model

from ecommerce.extensions.test import factories
from ecommerce.programs.benefits import PercentageDiscountBenefitWithoutRange
from ecommerce.programs.constants import BENEFIT_PROXY_CLASS_MAP
from ecommerce.programs.custom import class_path
from ecommerce.programs.tests.mixins import ProgramTestMixin
from ecommerce.tests.testcases import CacheMixin, TestCase

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class ViewTestMixin(CacheMixin):
    path = None

    def setUp(self):
        super(ViewTestMixin, self).setUp()
        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)

    def assert_get_response_status(self, status_code):
        """ Asserts the HTTP status of a GET responses matches the expected status. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, status_code)
        return response

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.assert_get_response_status(302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_staff_only(self):
        """ The view should only be accessible to staff. """
        self.client.logout()

        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        self.assert_get_response_status(404)

        user.is_staff = True
        user.save()
        self.assert_get_response_status(200)


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

        program_offers = factories.ProgramOfferFactory.create_batch(4)

        for offer in program_offers:
            self.mock_program_detail_endpoint(offer.condition.program_uuid)

        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), program_offers)

        # The page should load even if the Programs API is inaccessible
        httpretty.disable()
        response = self.assert_get_response_status(200)
        self.assertEqual(list(response.context['object_list']), program_offers)

    def test_get_queryset(self):
        """ Should return only Conditional Offers with Site offer type. """

        # Conditional Offer should contain a condition with program uuid set in order to be returned
        site_conditional_offer = factories.ProgramOfferFactory()
        program_offers = [
            site_conditional_offer,
            factories.ProgramOfferFactory(offer_type=ConditionalOffer.VOUCHER),
            factories.ConditionalOfferFactory(offer_type=ConditionalOffer.SITE)
        ]

        for offer in program_offers:
            self.mock_program_detail_endpoint(offer.condition.program_uuid)

        response = self.client.get(self.path)
        self.assertEqual(list(response.context['object_list']), [site_conditional_offer])


class ProgramOfferUpdateViewTests(ProgramTestMixin, ViewTestMixin, TestCase):
    def setUp(self):
        super(ProgramOfferUpdateViewTests, self).setUp()
        self.program_offer = factories.ProgramOfferFactory()
        self.path = reverse('programs:offers:edit', kwargs={'pk': self.program_offer.pk})

        # NOTE: We activate httpretty here so that we don't have to decorate every test method.
        httpretty.enable()
        self.mock_program_detail_endpoint(self.program_offer.condition.program_uuid)

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
            'benefit_type': BENEFIT_PROXY_CLASS_MAP[self.program_offer.benefit.proxy_class],
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
        self.mock_program_detail_endpoint(expected_uuid)
        expected_benefit_value = 10
        data = {
            'program_uuid': expected_uuid,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': expected_benefit_value,
        }
        response = self.client.post(self.path, data, follow=False)
        program_offer = ConditionalOffer.objects.get()

        self.assertRedirects(response, reverse('programs:offers:edit', kwargs={'pk': program_offer.pk}))
        self.assertIsNone(program_offer.start_datetime)
        self.assertIsNone(program_offer.end_datetime)
        self.assertEqual(program_offer.condition.program_uuid, expected_uuid)
        self.assertEqual(program_offer.benefit.type, '')
        self.assertEqual(program_offer.benefit.value, expected_benefit_value)
        self.assertEqual(program_offer.benefit.proxy_class, class_path(PercentageDiscountBenefitWithoutRange))

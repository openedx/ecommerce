# -*- coding: utf-8 -*-
import uuid

import httpretty
import mock
from oscar.core.loading import get_model

from ecommerce.extensions.test.factories import (
    ConditionalOfferFactory,
    JournalConditionFactory,
    PercentageDiscountBenefitWithoutRangeFactory
)
from ecommerce.journal.benefit_constants import BENEFIT_MAP
from ecommerce.journal.forms import JournalBundleOfferForm
from ecommerce.programs.custom import class_path
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class JournalBundleOfferFormTests(TestCase):

    def generate_data(self, **kwargs):
        """
        Create data for offer, and update it with the given data.
        """
        data = {
            'journal_bundle_uuid': uuid.uuid4(),
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 2,
        }
        data.update(**kwargs)
        return data

    def _assert_journal_bundle_offer_conditions(self, offer, journal_bundle_uuid, expected_benefit_value,
                                                expected_benefit_type, expected_name):
        """
        Assert the given offer's parameters with the expected values.
        """
        self.assertEqual(str(offer.name), expected_name)
        self.assertEqual(offer.offer_type, ConditionalOffer.SITE)
        self.assertEqual(offer.status, ConditionalOffer.OPEN)
        self.assertEqual(offer.max_basket_applications, 1)
        self.assertEqual(offer.site, self.site)
        self.assertEqual(offer.condition.journal_bundle_uuid, journal_bundle_uuid)
        self.assertEqual(offer.benefit.proxy_class, class_path(BENEFIT_MAP[expected_benefit_type]))
        self.assertEqual(offer.benefit.value, expected_benefit_value)

    def _assert_form_errors(self, data, expected_errors):
        """
        Assert that form validation fails with the expected errors.
        """
        form = JournalBundleOfferForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, expected_errors)

    def test_init(self):
        """
        Assert the init data from instance.
        """
        journal_offer = ConditionalOfferFactory(
            benefit=PercentageDiscountBenefitWithoutRangeFactory(),
            condition=JournalConditionFactory()
        )
        form = JournalBundleOfferForm(instance=journal_offer)
        self.assertEqual(form['journal_bundle_uuid'].value(), journal_offer.condition.journal_bundle_uuid.hex)
        self.assertEqual(form['benefit_type'].value(), journal_offer.benefit.proxy().benefit_class_type)
        self.assertEqual(form['benefit_value'].value(), journal_offer.benefit.value)

    def test_clean_percentage(self):
        """
        Assert that percentage can not be greater than 100.
        """
        data = self.generate_data(benefit_type=Benefit.PERCENTAGE, benefit_value=101)
        self._assert_form_errors(data, {'benefit_value': ['Percentage discounts cannot be greater than 100%.']})

    def test_clean_with_missing_start_date(self):
        """
        Assert that with end data, start date is required.
        """
        data = self.generate_data(end_datetime='2007-02-01 00:00:00')
        self._assert_form_errors(data,
                                 {'start_datetime': ['A start date must be specified when specifying an end date']})

    def test_clean_with_invalid_date_ordering(self):
        """
        Assert that start date should be earlier that end date.
        """
        data = self.generate_data(start_datetime='2017-01-02 00:00:00', end_datetime='2007-02-01 00:00:00')
        self._assert_form_errors(data, {'start_datetime': ['The start date must occur before the end date']})

    def test_clean_with_conflicting_journal_uuid(self):
        """
        Assert that an error should be raised if an offer already exists with same uuid and type.
        """
        journal_offer = ConditionalOfferFactory(
            benefit=PercentageDiscountBenefitWithoutRangeFactory(),
            condition=JournalConditionFactory()
        )
        data = self.generate_data(journal_bundle_uuid=journal_offer.condition.journal_bundle_uuid)
        self._assert_form_errors(data, {'journal_bundle_uuid': ['An offer already exists for this journal bundle']})

    @httpretty.activate
    @mock.patch('ecommerce.journal.forms.fetch_journal_bundle')
    def test_save_create(self, mock_discovery_call):
        """
        A new ConditionalOffer, Benefit, and Condition should be created.
        """
        mock_discovery_call.return_value = {"title": "test-journal"}
        data = self.generate_data()
        form = JournalBundleOfferForm(request=self.request, data=data)
        form.is_valid()
        offer = form.save()
        self._assert_journal_bundle_offer_conditions(offer, data['journal_bundle_uuid'], data['benefit_value'],
                                                     data['benefit_type'], 'Journal Bundle Offer: test-journal')

    @httpretty.activate
    @mock.patch('ecommerce.journal.forms.fetch_journal_bundle')
    def test_save_edit(self, mock_discovery_call):
        """
        Previously-created ConditionalOffer, Benefit, and Condition instances should be updated.
        """
        mock_discovery_call.return_value = {"title": "test-journal"}
        journal_offer = ConditionalOfferFactory(
            benefit=PercentageDiscountBenefitWithoutRangeFactory(),
            condition=JournalConditionFactory()
        )
        data = self.generate_data(
            journal_bundle_uuid=journal_offer.condition.journal_bundle_uuid,
            benefit_type=Benefit.FIXED
        )
        form = JournalBundleOfferForm(request=self.request, data=data, instance=journal_offer)
        form.is_valid()
        form.save()

        journal_offer.refresh_from_db()
        self._assert_journal_bundle_offer_conditions(journal_offer, data['journal_bundle_uuid'], data['benefit_value'],
                                                     data['benefit_type'], 'Journal Bundle Offer: test-journal')

    @httpretty.activate
    @mock.patch('ecommerce.journal.forms.fetch_journal_bundle')
    def test_save_without_commit(self, mock_discovery_call):
        """
        No data should be persisted to the database if the commit kwarg is set to False.
        """
        mock_discovery_call.return_value = {"title": "test-journal"}
        data = self.generate_data()
        form = JournalBundleOfferForm(request=self.request, data=data)
        form.is_valid()
        instance = form.save(commit=False)
        self.assertIsNone(instance)

    def test_create_when_conditional_offer_with_uuid_exists(self):
        """
        Verify a journal bundle offer can be created if a conditional offer with different type and same uuid already
        exists.
        """
        data = self.generate_data()
        ConditionalOfferFactory(
            benefit=PercentageDiscountBenefitWithoutRangeFactory(),
            condition__journal_bundle_uuid=data['journal_bundle_uuid'],
            offer_type=ConditionalOffer.VOUCHER,
        )
        form = JournalBundleOfferForm(request=self.request, data=data)
        self.assertTrue(form.is_valid())

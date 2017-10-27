# -*- coding: utf-8 -*-
import uuid

import httpretty
from oscar.core.loading import get_model

from ecommerce.enterprise.constants import BENEFIT_MAP
from ecommerce.enterprise.forms import EnterpriseOfferForm
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE
from ecommerce.extensions.test import factories
from ecommerce.programs.custom import class_path
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class EnterpriseOfferFormTests(EnterpriseServiceMockMixin, TestCase):
    def generate_data(self, **kwargs):
        data = {
            'enterprise_customer_uuid': uuid.uuid4(),
            'enterprise_customer_name': 'BigEnterprise',
            'enterprise_customer_catalog_uuid': uuid.uuid4(),
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 22,
        }
        data.update(**kwargs)
        return data

    def assert_enterprise_offer_conditions(self, offer, enterprise_customer_uuid, enterprise_customer_name,
                                           enterprise_customer_catalog_uuid, expected_benefit_value,
                                           expected_benefit_type, expected_name):
        """ Assert the given offer's parameters match the expected values. """
        self.assertEqual(str(offer.name), expected_name)
        self.assertEqual(offer.offer_type, ConditionalOffer.SITE)
        self.assertEqual(offer.status, ConditionalOffer.OPEN)
        self.assertEqual(offer.max_basket_applications, 1)
        self.assertEqual(offer.site, self.site)
        self.assertEqual(offer.priority, OFFER_PRIORITY_ENTERPRISE)
        self.assertEqual(offer.condition.enterprise_customer_uuid, enterprise_customer_uuid)
        self.assertEqual(offer.condition.enterprise_customer_name, enterprise_customer_name)
        self.assertEqual(offer.condition.enterprise_customer_catalog_uuid, enterprise_customer_catalog_uuid)
        self.assertEqual(offer.benefit.proxy_class, class_path(BENEFIT_MAP[expected_benefit_type]))
        self.assertEqual(offer.benefit.value, expected_benefit_value)

    def assert_form_errors(self, data, expected_errors):
        """ Assert that form validation fails with the expected errors. """
        form = EnterpriseOfferForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, expected_errors)

    def test_init(self):
        """ The constructor should pull initial data from the passed-in instance. """
        enterprise_offer = factories.EnterpriseOfferFactory()
        form = EnterpriseOfferForm(instance=enterprise_offer)
        self.assertEqual(
            form['enterprise_customer_uuid'].value(),
            enterprise_offer.condition.enterprise_customer_uuid.hex
        )
        self.assertEqual(
            form['enterprise_customer_catalog_uuid'].value(),
            enterprise_offer.condition.enterprise_customer_catalog_uuid.hex
        )
        self.assertEqual(form['benefit_type'].value(), enterprise_offer.benefit.proxy().benefit_class_type)
        self.assertEqual(form['benefit_value'].value(), enterprise_offer.benefit.value)

    def test_clean_percentage(self):
        """ If a percentage benefit type is specified, the benefit value must never be greater than 100. """
        data = self.generate_data(benefit_type=Benefit.PERCENTAGE, benefit_value=101)
        self.assert_form_errors(data, {'benefit_value': ['Percentage discounts cannot be greater than 100%.']})

    def test_clean_with_missing_start_date(self):
        """ If an end date is specified, a start date must also be specified. """
        data = self.generate_data(end_datetime='2017-01-01 00:00:00')
        self.assert_form_errors(
            data,
            {'start_datetime': ['A start date must be specified when specifying an end date.']}
        )

    def test_clean_with_invalid_date_ordering(self):
        """ The start date must always occur before the end date. """
        data = self.generate_data(start_datetime='2017-01-02 00:00:00', end_datetime='2017-01-01 00:00:00')
        self.assert_form_errors(data, {'start_datetime': ['The start date must occur before the end date.']})

    def test_clean_with_conflicting_enterprise_customer_and_catalog_uuids(self):
        """ If an offer already exists for the given Enterprise and Catalog, an error should be raised. """
        offer = factories.EnterpriseOfferFactory()
        data = self.generate_data(
            enterprise_customer_uuid=offer.condition.enterprise_customer_uuid,
            enterprise_customer_name=offer.condition.enterprise_customer_name,
            enterprise_customer_catalog_uuid=offer.condition.enterprise_customer_catalog_uuid,
        )
        self.assert_form_errors(
            data,
            {
                'enterprise_customer_uuid': [
                    'An offer already exists for this Enterprise & Catalog combination.'
                ],
                'enterprise_customer_catalog_uuid': [
                    'An offer already exists for this Enterprise & Catalog combination.'
                ]
            }
        )

    @httpretty.activate
    def test_save_create(self):
        """ A new ConditionalOffer, Benefit, and Condition should be created. """
        data = self.generate_data()
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])
        form = EnterpriseOfferForm(request=self.request, data=data)
        form.is_valid()
        offer = form.save()
        self.assert_enterprise_offer_conditions(
            offer,
            data['enterprise_customer_uuid'],
            data['enterprise_customer_name'],
            data['enterprise_customer_catalog_uuid'],
            data['benefit_value'],
            data['benefit_type'],
            'Discount provided by {}.'.format(data['enterprise_customer_name']),
        )

    @httpretty.activate
    def test_save_create_special_char_title(self):
        """ When the Enterprise's name is international, new objects should still be created."""
        enterprise_customer_uuid = uuid.uuid4()
        data = self.generate_data(
            enterprise_customer_uuid=enterprise_customer_uuid,
            enterprise_customer_name=u'Sp\xe1nish Enterprise',
        )
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'], name=u'Sp\xe1nish Enterprise')
        form = EnterpriseOfferForm(request=self.request, data=data)
        form.is_valid()
        offer = form.save()
        self.assert_enterprise_offer_conditions(
            offer,
            data['enterprise_customer_uuid'],
            data['enterprise_customer_name'],
            data['enterprise_customer_catalog_uuid'],
            data['benefit_value'],
            data['benefit_type'],
            'Discount provided by Spánish Enterprise.'
        )

    @httpretty.activate
    def test_save_edit(self):
        """ Previously-created ConditionalOffer, Benefit, and Condition instances should be updated. """
        offer = factories.EnterpriseOfferFactory()
        data = self.generate_data(
            enterprise_customer_uuid=offer.condition.enterprise_customer_uuid,
            benefit_type=Benefit.FIXED
        )
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])
        form = EnterpriseOfferForm(request=self.request, data=data, instance=offer)
        form.is_valid()
        form.save()

        offer.refresh_from_db()
        self.assert_enterprise_offer_conditions(
            offer,
            data['enterprise_customer_uuid'],
            data['enterprise_customer_name'],
            data['enterprise_customer_catalog_uuid'],
            data['benefit_value'],
            data['benefit_type'],
            'Discount provided by {}.'.format(data['enterprise_customer_name']),
        )

    @httpretty.activate
    def test_save_without_commit(self):
        """ No data should be persisted to the database if the commit kwarg is set to False. """
        data = self.generate_data()
        form = EnterpriseOfferForm(request=self.request, data=data)
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])
        form.is_valid()
        instance = form.save(commit=False)
        self.assertIsNone(instance.pk)
        self.assertFalse(hasattr(instance, 'benefit'))
        self.assertFalse(hasattr(instance, 'condition'))

    @httpretty.activate
    def test_save_offer_name(self):
        """ If a request object is sent, the offer name should include the enterprise name. """
        data = self.generate_data()
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])
        form = EnterpriseOfferForm(request=self.request, data=data)
        form.is_valid()
        offer = form.save()
        self.assert_enterprise_offer_conditions(
            offer,
            data['enterprise_customer_uuid'],
            data['enterprise_customer_name'],
            data['enterprise_customer_catalog_uuid'],
            data['benefit_value'],
            data['benefit_type'],
            'Discount provided by {}.'.format(data['enterprise_customer_name']),
        )

    def test_create_when_conditional_offer_with_uuid_exists(self):
        """
        An Enterprise Offer can be created if a conditional offer with different type and same UUIDs already exists.
        """
        data = self.generate_data()
        factories.EnterpriseOfferFactory(
            condition__enterprise_customer_uuid=data['enterprise_customer_uuid'],
            condition__enterprise_customer_name=data['enterprise_customer_name'],
            condition__enterprise_customer_catalog_uuid=data['enterprise_customer_catalog_uuid'],
            offer_type=ConditionalOffer.VOUCHER,
        )
        form = EnterpriseOfferForm(request=self.request, data=data)
        self.assertTrue(form.is_valid())

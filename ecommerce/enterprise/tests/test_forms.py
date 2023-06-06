# -*- coding: utf-8 -*-


import uuid

import ddt
import responses
from oscar.core.loading import get_model
from oscar.test.factories import OrderDiscountFactory, OrderFactory

from ecommerce.enterprise.benefits import BENEFIT_MAP
from ecommerce.enterprise.forms import EnterpriseOfferForm
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.refund.status import REFUND
from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.extensions.test import factories
from ecommerce.programs.custom import class_path
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


@ddt.ddt
class EnterpriseOfferFormTests(EnterpriseServiceMockMixin, TestCase):

    def setUp(self):
        super(EnterpriseOfferFormTests, self).setUp()
        self.contract_discount_type = EnterpriseContractMetadata.PERCENTAGE
        self.contract_discount_value = 74
        self.prepaid_invoice_amount = 998990
        self.user = UserFactory()

    def generate_data(self, **kwargs):
        data = {
            'enterprise_customer_uuid': uuid.uuid4(),
            'enterprise_customer_name': 'BigEnterprise',
            'enterprise_customer_catalog_uuid': uuid.uuid4(),
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 22,
            'contract_discount_type': self.contract_discount_type,
            'contract_discount_value': self.contract_discount_value,
            'prepaid_invoice_amount': self.prepaid_invoice_amount,
            'sales_force_id': '006abcde0123456789',
            'salesforce_opportunity_line_item': '000abcde9876543210',
            'max_global_applications': 2,
            'max_discount': 300,
            'max_user_discount': 50,
            'max_user_applications': 3,
            'usage_email_frequency': ConditionalOffer.DAILY
        }
        data.update(**kwargs)
        return data

    def assert_enterprise_offer_conditions(self, offer, enterprise_customer_uuid, enterprise_customer_name,
                                           enterprise_customer_catalog_uuid, expected_benefit_value,
                                           expected_benefit_type, expected_name, expected_contract_discount_type,
                                           expected_contract_discount_value, expected_prepaid_invoice_amount,
                                           expected_sales_force_id, expected_salesforce_opportunity_line_item,
                                           expected_max_global_applications, expected_max_discount,
                                           expected_max_user_applications, expected_max_user_discount):
        """ Assert the given offer's parameters match the expected values. """
        self.assertEqual(str(offer.name), expected_name)
        self.assertEqual(offer.offer_type, ConditionalOffer.SITE)
        self.assertEqual(offer.sales_force_id, expected_sales_force_id)
        self.assertEqual(offer.salesforce_opportunity_line_item, expected_salesforce_opportunity_line_item)
        self.assertEqual(offer.status, ConditionalOffer.OPEN)
        self.assertEqual(offer.max_basket_applications, 1)
        self.assertEqual(offer.partner, self.partner)
        self.assertEqual(offer.priority, OFFER_PRIORITY_ENTERPRISE)
        self.assertEqual(offer.condition.enterprise_customer_uuid, enterprise_customer_uuid)
        self.assertEqual(offer.condition.enterprise_customer_name, enterprise_customer_name)
        self.assertEqual(offer.condition.enterprise_customer_catalog_uuid, enterprise_customer_catalog_uuid)
        self.assertEqual(offer.benefit.proxy_class, class_path(BENEFIT_MAP[expected_benefit_type]))
        self.assertEqual(offer.benefit.value, expected_benefit_value)
        self.assertEqual(
            offer.enterprise_contract_metadata.discount_type,
            expected_contract_discount_type
        )
        self.assertEqual(
            offer.enterprise_contract_metadata.discount_value,
            expected_contract_discount_value
        )
        self.assertEqual(
            offer.enterprise_contract_metadata.amount_paid,
            expected_prepaid_invoice_amount
        )
        self.assertEqual(offer.max_global_applications, expected_max_global_applications)
        self.assertEqual(offer.max_discount, expected_max_discount)
        self.assertEqual(offer.max_user_applications, expected_max_user_applications)
        self.assertEqual(offer.max_user_discount, expected_max_user_discount)

    def assert_form_errors(self, data, expected_errors, instance=None):
        """ Assert that form validation fails with the expected errors. """
        form = EnterpriseOfferForm(data=data, instance=instance)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, expected_errors)

    def test_init(self):
        """ The constructor should pull initial data from the passed-in instance. """
        enterprise_offer = factories.EnterpriseOfferFactory()
        ecm = EnterpriseContractMetadata(
            discount_value=25,
            discount_type=EnterpriseContractMetadata.PERCENTAGE,
            amount_paid=12345
        )
        enterprise_offer.enterprise_contract_metadata = ecm
        enterprise_offer.max_global_applications = 2
        enterprise_offer.max_discount = 300
        enterprise_offer.max_user_applications = 2
        enterprise_offer.max_user_discount = 30
        form = EnterpriseOfferForm(instance=enterprise_offer)
        self.assertEqual(
            uuid.UUID(form['enterprise_customer_uuid'].value()),
            enterprise_offer.condition.enterprise_customer_uuid
        )
        self.assertEqual(
            uuid.UUID(form['enterprise_customer_catalog_uuid'].value()),
            enterprise_offer.condition.enterprise_customer_catalog_uuid
        )
        self.assertEqual(form['benefit_type'].value(), enterprise_offer.benefit.proxy().benefit_class_type)
        self.assertEqual(form['benefit_value'].value(), enterprise_offer.benefit.value)
        self.assertEqual(form['contract_discount_type'].value(), EnterpriseContractMetadata.PERCENTAGE)
        self.assertEqual(form['contract_discount_value'].value(), 25)
        self.assertEqual(form['prepaid_invoice_amount'].value(), 12345)
        self.assertEqual(form['max_global_applications'].value(), 2)
        self.assertEqual(form['max_discount'].value(), 300)
        self.assertEqual(form['max_user_applications'].value(), 2)
        self.assertEqual(form['max_user_discount'].value(), 30)

    def test_contract_metadata_required_on_create(self):
        """
        Contract metadata should be required on create, specifically the
        contract discount type and value fields.
        """
        enterprise_offer = factories.EnterpriseOfferFactory()
        form = EnterpriseOfferForm(instance=enterprise_offer)
        self.assertTrue(form['contract_discount_type'].field.required)
        self.assertTrue(form['contract_discount_value'].field.required)

    def test_contract_metadata_required_on_edit(self):
        """
        Contract metadata should be required on edit, specifically the
        contract discount type and value fields.
        """
        enterprise_offer = factories.EnterpriseOfferFactory()
        form = EnterpriseOfferForm(instance=enterprise_offer)
        self.assertTrue(form['contract_discount_type'].field.required)
        self.assertTrue(form['contract_discount_value'].field.required)

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

    def test_clean_with_invalid_contract_value_percentage(self):
        """
        The contract discount value, when the contract discount type is a
        percentage, should not be greater than 100.
        """
        data = self.generate_data(contract_discount_value=120)
        self.assert_form_errors(
            data,
            {'contract_discount_value': ['Percentage discounts cannot be greater than 100%.']},
        )

    def test_clean_with_invalid_contract_value_absolute(self):
        """
        The contract discount value, when the contract discount type is an
        absolute value, should not have more digits before/after the decimal.
        """
        # too many digits after decimal
        data = self.generate_data(
            contract_discount_type=EnterpriseContractMetadata.FIXED,
            contract_discount_value=10000.12345,
        )
        self.assert_form_errors(
            data,
            {'contract_discount_value': ['More than 2 digits after the decimal not allowed for absolute value.']},
        )

    def test_clean_with_missing_prepaid_invoice_amount(self):
        """
        The prepaid invoice amount is required when the contract discount
        type is an absolute value.
        """
        data = self.generate_data(
            contract_discount_type=EnterpriseContractMetadata.FIXED,
            contract_discount_value=10000,
            prepaid_invoice_amount=None,
        )
        self.assert_form_errors(
            data,
            {'prepaid_invoice_amount': ['This field is required when contract discount type is absolute.']},
        )

    @responses.activate
    def test_save_create(self):
        """
        A new ConditionalOffer, Benefit, Condition, and
        EnterpriseContractMetadata should be created.
        """
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
            'Discount of type {} provided by {} for {}.'.format(
                ConditionalOffer.SITE,
                data['enterprise_customer_name'][:48],
                data['enterprise_customer_catalog_uuid']
            ),
            data['contract_discount_type'],
            data['contract_discount_value'],
            data['prepaid_invoice_amount'],
            data['sales_force_id'],
            data['salesforce_opportunity_line_item'],
            data['max_global_applications'],
            data['max_discount'],
            data['max_user_applications'],
            data['max_user_discount'],
        )

    @responses.activate
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
            'Discount of type Site provided by Spánish Enterprise for {}.'.format(
                data['enterprise_customer_catalog_uuid']
            ),
            data['contract_discount_type'],
            data['contract_discount_value'],
            data['prepaid_invoice_amount'],
            data['sales_force_id'],
            data['salesforce_opportunity_line_item'],
            data['max_global_applications'],
            data['max_discount'],
            data['max_user_applications'],
            data['max_user_discount'],
        )

    @responses.activate
    def test_save_edit(self):
        """ Previously-created ConditionalOffer, Benefit, and Condition instances should be updated. """
        offer = factories.EnterpriseOfferFactory()
        ecm = EnterpriseContractMetadata(
            discount_value=self.contract_discount_value,
            discount_type=self.contract_discount_type,
            amount_paid=self.prepaid_invoice_amount,
        )
        offer.enterprise_contract_metadata = ecm
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
            'Discount of type {} provided by {} for {}.'.format(
                ConditionalOffer.SITE,
                data['enterprise_customer_name'][:48],
                data['enterprise_customer_catalog_uuid']
            ),
            data['contract_discount_type'],
            data['contract_discount_value'],
            data['prepaid_invoice_amount'],
            data['sales_force_id'],
            data['salesforce_opportunity_line_item'],
            data['max_global_applications'],
            data['max_discount'],
            data['max_user_applications'],
            data['max_user_discount'],
        )

    @responses.activate
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

    @responses.activate
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
            'Discount of type {} provided by {} for {}.'.format(
                ConditionalOffer.SITE,
                data['enterprise_customer_name'][:48],
                data['enterprise_customer_catalog_uuid']
            ),
            data['contract_discount_type'],
            data['contract_discount_value'],
            data['prepaid_invoice_amount'],
            data['sales_force_id'],
            data['salesforce_opportunity_line_item'],
            data['max_global_applications'],
            data['max_discount'],
            data['max_user_applications'],
            data['max_user_discount'],
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

    def test_offer_form_help_text_and_labels(self):
        """
        Verify that `help_text` and `label` are correct for enterprise offer form fields.
        """
        data = self.generate_data()
        factories.EnterpriseOfferFactory()
        form = EnterpriseOfferForm(request=self.request, data=data)
        self.assertEqual(form.fields['max_global_applications'].label, 'Enrollment Limit')
        self.assertEqual(form.fields['max_discount'].label, 'Bookings Limit')
        self.assertEqual(
            form.fields['max_global_applications'].help_text,
            'The maximum number of enrollments that can redeem this offer.'
        )
        self.assertEqual(
            form.fields['max_discount'].help_text,
            'The maximum USD dollar amount that can be redeemed by this offer.'
        )
        self.assertEqual(form.fields['max_discount'].widget.attrs['min'], 0)
        self.assertEqual(form.fields['max_user_applications'].label, 'Per User Enrollment Limit')
        self.assertEqual(form.fields['max_user_discount'].label, 'Per User Bookings Limit')
        self.assertEqual(
            form.fields['max_user_applications'].help_text,
            'The maximum number of enrollments, by a user, that can redeem this offer.'
        )
        self.assertEqual(
            form.fields['max_user_discount'].help_text,
            'The maximum USD dollar amount that can be redeemed using this offer by a user.'
        )
        self.assertEqual(form.fields['max_user_discount'].widget.attrs['min'], 0)

    def test_max_global_applications_clean(self):
        """
        Verify that `clean` for `max_global_applications` field is working as expected.
        """
        num_applications = 3
        expected_errors = {
            'max_global_applications': [
                'Ensure new value must be greater than or equal to consumed({}) value.'.format(num_applications)
            ]
        }
        # create an enterprise offer that can be used upto 5 times and has already been used 3 times
        offer = factories.EnterpriseOfferFactory(max_global_applications=5, num_applications=num_applications)
        # now try to update the offer with max_global_applications set to 2
        # which is less than the number of times this offer has already been used
        data = self.generate_data(max_global_applications=2)
        self.assert_form_errors(data, expected_errors, instance=offer)

    def _test_sales_force_id(self, sales_force_id, expected_error, is_update_view):
        """
        Verify that `clean` for `sales_force_id` field is working as expected.
        """
        instance = None
        if is_update_view:
            instance = factories.EnterpriseOfferFactory()
        data = self.generate_data(sales_force_id=sales_force_id)
        if expected_error:
            expected_errors = {'sales_force_id': [expected_error]}
            self.assert_form_errors(data, expected_errors, instance)
        else:
            form = EnterpriseOfferForm(data=data, instance=instance)
            self.assertTrue(form.is_valid())

    @ddt.data(
        # Valid Cases
        ('006abcde0123456789', None),
        ('006ABCDE0123456789', None),
        ('none', None),
        # Invalid Cases
        ('006ABCDE012345678123143', 'Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006.'),
        ('006ABCDE01234', 'Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006.'),
        ('007ABCDE0123456789', 'Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006.'),
        ('006ABCDE0 12345678', 'Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006.'),
    )
    @ddt.unpack
    def test_sales_force_id(self, sales_force_id, expected_error):
        """
        Verify that `clean` for `sales_force_id` field is working as expected.
        """
        self._test_sales_force_id(sales_force_id, expected_error, is_update_view=False)
        self._test_sales_force_id(sales_force_id, expected_error, is_update_view=True)

    def _test_salesforce_opportunity_line_item(self, salesforce_opportunity_line_item, expected_error, is_update_view):
        """
        Verify that `clean` for `salesforce_opportunity_line_item` field is working as expected.
        """
        instance = None
        if is_update_view:
            instance = factories.EnterpriseOfferFactory()
        data = self.generate_data(salesforce_opportunity_line_item=salesforce_opportunity_line_item)
        if expected_error:
            expected_errors = {'salesforce_opportunity_line_item': [expected_error]}
            self.assert_form_errors(data, expected_errors, instance)
        else:
            form = EnterpriseOfferForm(data=data, instance=instance)
            self.assertTrue(form.is_valid())

    @ddt.data(
        # Valid Cases
        ('006abcde0123456789', None),
        ('006ABCDE0123456789', None),
        ('none', None),
        # Invalid Cases
        ('006ABCDE012345678123143',
         'The Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number.'),
        ('006ABCDE01234',
         'The Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number.'),
        ('a07ABCDE0123456789',
         'The Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number.'),
        ('006ABCDE0 12345678',
         'The Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number.'),
    )
    @ddt.unpack
    def test_salesforce_opportunity_line_item(self, salesforce_opportunity_line_item, expected_error):
        """
        Verify that `clean` for `salesforce_opportunity_line_item` field is working as expected.
        """
        self._test_salesforce_opportunity_line_item(
            salesforce_opportunity_line_item, expected_error, is_update_view=False)
        self._test_salesforce_opportunity_line_item(
            salesforce_opportunity_line_item, expected_error, is_update_view=True)

    def test_max_discount_clean_with_negative_value(self):
        """
        Verify that `clean` for `max_discount` field raises correct error for negative values.
        """
        expected_errors = {
            'max_discount': [
                'Ensure this value is greater than or equal to 0.'
            ]
        }
        data = self.generate_data(max_discount=-100)
        self.assert_form_errors(data, expected_errors)

    def test_max_discount_clean_with_incorrect_value(self):
        """
        Verify that `clean` for `max_discount` field raises correct error for values less than consumed discount.
        """
        total_discount = 400
        expected_errors = {
            'max_discount': [
                'Ensure new value must be greater than or equal to consumed({:.2f}) value.'.format(total_discount)
            ]
        }
        # create an enterprise offer that can provide max $500 discount and has already consumed $400
        offer = factories.EnterpriseOfferFactory(max_discount=500, total_discount=total_discount)
        # now try to update the offer with max_discount set to 300 which is less than the already consumed discount
        data = self.generate_data(max_discount=300)
        self.assert_form_errors(data, expected_errors, instance=offer)

    @responses.activate
    def test_offer_form_with_increased_values(self):
        """
        Verify that an existing enterprise offer can be updated with increased values.
        """
        data = self.generate_data(max_global_applications=40, max_discount=7000)
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])

        # create an enterprise offer with both max_global_applications and max_discount
        factories.EnterpriseOfferFactory(
            max_global_applications=30,
            num_applications=10,
            max_discount=5000,
            total_discount=1000
        )
        # now try to update the offer with increased values
        form = EnterpriseOfferForm(request=self.request, data=data)
        self.assertTrue(form.is_valid())
        offer = form.save()
        self.assertEqual(offer.max_global_applications, data['max_global_applications'])
        self.assertEqual(offer.max_discount, data['max_discount'])

    @ddt.data(
        {
            'offer_data': {'max_global_applications': 30, 'num_applications': 20},
            'offer_attr': 'num_applications',
            'offer_value': 30
        },
        {
            'offer_data': {'max_discount': 3000, 'total_discount': 2000},
            'offer_attr': 'total_discount',
            'offer_value': 3000
        }
    )
    @ddt.unpack
    def test_offer_availability(self, offer_data, offer_attr, offer_value):
        """
        Verify that enterprise offer has correct availability status based on
        max_global_applications and max_discount values.
        """
        offer = factories.EnterpriseOfferFactory(**offer_data)

        offer = ConditionalOffer.objects.get(id=offer.id)
        self.assertTrue(offer.is_available())

        # set new value to make the offer consumed
        setattr(offer, offer_attr, offer_value)
        offer.save()

        offer = ConditionalOffer.objects.get(id=offer.id)
        self.assertFalse(offer.is_available())

    def test_max_user_applications_clean(self):
        """
        Verify that `clean` for `max_user_applications` field is working as expected.
        """
        num_applications = 3
        expected_errors = {
            'max_user_applications': [
                'Ensure new value must be greater than or equal to consumed({}) value.'.format(num_applications)
            ]
        }
        # create an enterprise offer that can be used upto 5 times and has already been used 3 times
        offer = factories.EnterpriseOfferFactory(max_user_applications=5, max_user_discount=500)
        for _ in range(num_applications):
            order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
            OrderDiscountFactory(order=order, offer_id=offer.id, amount=10)
        # now try to update the offer with max_user_applications set to 2
        # which is less than the number of times this offer has already been used
        data = self.generate_data(max_user_applications=2)
        self.assert_form_errors(data, expected_errors, instance=offer)

    def test_max_user_discount_clean_with_negative_value(self):
        """
        Verify that `clean` for `max_user_discount` field raises correct error for negative values.
        """
        expected_errors = {
            'max_user_discount': [
                'Ensure this value is greater than or equal to 0.'
            ]
        }
        data = self.generate_data(max_user_discount=-100)
        self.assert_form_errors(data, expected_errors)

    def test_max_user_discount_clean_with_incorrect_value(self):
        """
        Verify that `clean` for `max_user_discount` field raises correct error for values less than consumed discount.
        """
        expected_errors = {
            'max_user_discount': [
                'Ensure new value must be greater than or equal to consumed(400.00) value.'
            ]
        }
        # create an enterprise offer that can provide max $500 discount and has already consumed $400
        offer = factories.EnterpriseOfferFactory(max_user_applications=50, max_user_discount=500)
        for _ in range(4):
            order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
            OrderDiscountFactory(order=order, offer_id=offer.id, amount=100)
        # now try to update the offer with max_discount set to 300 which is less than the already consumed discount
        data = self.generate_data(max_user_applications=50, max_user_discount=300)
        self.assert_form_errors(data, expected_errors, instance=offer)

    @responses.activate
    def test_max_user_discount_clean_with_refunded_enrollments(self):
        """
        Verify that `clean` for `max_user_discount` and `max_user_applications` does not raise error when total consumed
         discount and total max user applications after refund is still less than the value, and the existing offer
         updates with new per user limit and max user application values.
        """
        current_refund_count = 0
        data = self.generate_data(max_user_applications=3, max_user_discount=300)
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])
        # create an enterprise offer that can provide max $500 discount and consume $400
        offer = factories.EnterpriseOfferFactory(max_user_applications=5, max_user_discount=500)
        for _ in range(4):
            order = OrderFactory(user=self.user, status=ORDER.COMPLETE)
            OrderDiscountFactory(order=order, offer_id=offer.id, amount=100)
            # create a refund of $200 so the total consumed discount becomes $200
            if current_refund_count < 2:
                RefundFactory(order=order, user=self.user, status=REFUND.COMPLETE)
                current_refund_count += 1
        # now try to update the offer with max_user_discount set to $300
        # which is still greater than the consumed discount after refund $200
        form = EnterpriseOfferForm(request=self.request, data=data, instance=offer)
        self.assertTrue(form.is_valid())
        offer = form.save()
        self.assertEqual(offer.max_user_applications, data['max_user_applications'])
        self.assertEqual(offer.max_user_discount, data['max_user_discount'])

    @responses.activate
    def test_offer_form_with_per_user_increased_limits(self):
        """
        Verify that an existing enterprise offer can be updated with per user increased limits.
        """
        data = self.generate_data(max_user_applications=40, max_user_discount=7000)
        self.mock_specific_enterprise_customer_api(data['enterprise_customer_uuid'])

        # create an enterprise offer with both max_global_applications and max_discount
        offer = factories.EnterpriseOfferFactory(
            max_user_applications=30,
            max_user_discount=5000
        )
        # now try to update the offer with increased values
        form = EnterpriseOfferForm(request=self.request, data=data, instance=offer)
        self.assertTrue(form.is_valid())
        offer = form.save()
        self.assertEqual(offer.max_user_applications, data['max_user_applications'])
        self.assertEqual(offer.max_user_discount, data['max_user_discount'])

    @ddt.data(
        {
            'emails_for_usage_alert': 'dummy@example.com, dummy1@example.com',
            'is_valid_form': True,
            'expected_errors': ''
        },
        {
            'emails_for_usage_alert': 'dummyexample.com, dummy1@example.com',
            'is_valid_form': False,
            'expected_errors': ['Given email address dummyexample.com is not a valid email.']
        },
        {
            'emails_for_usage_alert': 'dummy@example.com : dummy1@example.com',
            'is_valid_form': False,
            'expected_errors': ['Given email address dummy@example.com : dummy1@example.com is not a valid email.']
        },
    )
    @ddt.unpack
    def test_emails_for_usage_alert(self, emails_for_usage_alert, is_valid_form, expected_errors):
        """
        Test emails_for_usage_alert field with valid and invalid data
        """
        data = self.generate_data(emails_for_usage_alert=emails_for_usage_alert)
        form = EnterpriseOfferForm(data=data)
        if is_valid_form:
            self.assertTrue(form.is_valid())
        else:
            self.assert_form_errors(data, {'emails_for_usage_alert': expected_errors})

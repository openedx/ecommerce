from __future__ import unicode_literals

import ddt
from oscar.test import factories

from ecommerce.extensions.payment.forms import PaymentForm
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class CyberSourceSubmitFormTests(TestCase):
    def setUp(self):
        super(CyberSourceSubmitFormTests, self).setUp()
        self.user = self.create_user()
        self.basket = factories.create_basket()
        self.basket.owner = self.user
        self.basket.save()

    def _generate_data(self, **kwargs):
        data = {
            'basket': self.basket.id,
            'first_name': 'Test',
            'last_name': 'User',
            'address_line1': '141 Portland Ave.',
            'address_line2': 'Floor 9',
            'city': 'Cambridge',
            'state': 'MA',
            'postal_code': '02139',
            'country': 'US',
        }
        data.update(**kwargs)
        return data

    def _assert_form_validity(self, is_valid, **kwargs):
        data = self._generate_data(**kwargs)
        self.assertEqual(PaymentForm(user=self.user, data=data).is_valid(), is_valid)

    def assert_form_valid(self, **kwargs):
        self._assert_form_validity(True, **kwargs)

    def assert_form_not_valid(self, **kwargs):
        self._assert_form_validity(False, **kwargs)

    def test_country_validation(self):
        """ Verify the country field is limited to valid ISO 3166 2-character country codes. """
        self.assert_form_valid(country='US')
        self.assert_form_not_valid(country='ZZ')
        self.assert_form_not_valid(country='ABC')

    @ddt.unpack
    @ddt.data(
        ('US', 'TX'),
        ('CA', 'QC')
    )
    def test_state_validation_for_north_america(self, country, valid_state):
        """ Verify the state field is limited to 2 characters when the country is set to the U.S. or Canada. """
        self.assert_form_valid(country=country, state=valid_state)
        self.assert_form_not_valid(country=country, state='ZZ')
        self.assert_form_not_valid(country=country, state=None)
        self.assert_form_not_valid(country=country, state='')

        data = self._generate_data(country=country)
        data.pop('state', None)
        self.assertFalse(PaymentForm(user=self.user, data=data).is_valid())

    def test_state_validation_outside_north_america(self):
        """ Verify the state field is limited to 60 characters when the country is NOT set to the U.S. or Canada. """
        self.assert_form_valid(country='GH', state=None)
        self.assert_form_valid(country='GH', state='Brong-Ahafo')

        invalid_state = ''.join(['a' for __ in range(0, 61)])
        self.assert_form_not_valid(country='GH', state=invalid_state)

    @ddt.unpack
    @ddt.data(
        ('US', 'CA'),
        ('CA', 'QC')
    )
    def test_postal_code_validation_for_north_america(self, country, valid_state):
        """ Verify the postal code is limited to 9 characters when the country is set to the U.S. or Canada. """
        self.assert_form_valid(country=country, state=valid_state, postal_code='90210')
        self.assert_form_valid(country=country, state=valid_state, postal_code='902102938')
        self.assert_form_not_valid(country=country, state=valid_state, postal_code='1234567890')
        self.assert_form_not_valid(country=country, state=valid_state, postal_code='')
        self.assert_form_not_valid(country=country, state=valid_state, postal_code=None)

    def test_postal_code_validation_outside_north_america(self):
        """ Verify the postal code field is limited to 10 characters when the country is
        NOT set to the U.S. or Canada. """
        self.assert_form_valid(country='IN', postal_code=None)
        self.assert_form_valid(country='IN', postal_code='1947')

        invalid_postal_code = ''.join(['a' for __ in range(0, 11)])
        self.assert_form_not_valid(country='IN', postal_code=invalid_postal_code)

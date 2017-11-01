from __future__ import unicode_literals

import ddt
import pycountry
from waffle.models import Switch

from ecommerce.extensions.payment.forms import PaymentForm
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class PaymentFormTests(TestCase):
    def setUp(self):
        super(PaymentFormTests, self).setUp()
        self.user = self.create_user()
        self.basket = create_basket(owner=self.user)

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
        self.assertEqual(PaymentForm(user=self.user, data=data, request=self.request).is_valid(), is_valid)

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
        self.assertFalse(PaymentForm(user=self.user, data=data, request=self.request).is_valid())

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

    # Temporarily add this test for codecov for the feature flag added for this test
    # https://openedx.atlassian.net/browse/LEARNER-2355
    # This code will be removed after this test is done
    def test_state_validation_with_optional_location_fields(self):
        """ Verify the state field is limited to 2 characters when the country is set to the U.S. or Canada. """
        switch, __ = Switch.objects.get_or_create(name='optional_location_fields')
        switch.active = True
        switch.save()
        self.assert_form_valid(country='US', state='CA')
        self.assert_form_not_valid(country='US', state='ZZ')
        self.assert_form_valid(country='US', state=None)
        self.assert_form_valid(country='US', state=None, address_line1=None)
        switch.active = False
        switch.save()
        self.assert_form_not_valid(country='US', state=None)
        self.assert_form_not_valid(country='US', state='CA', address_line1=None)

    # Temporarily add this test for codecov for the feature flag added for this test
    # https://openedx.atlassian.net/browse/LEARNER-2355
    # This code will be removed after this test is done
    def test_postal_code_validation_optional_location_fields(self):
        """ Verify the postal code is limited to 9 characters when the country is set to the U.S. or Canada. """
        switch, __ = Switch.objects.get_or_create(name='optional_location_fields')
        switch.active = True
        switch.save()
        self.assert_form_valid(country='US', state='CA', postal_code='90210')
        self.assert_form_valid(country='US', state='CA', postal_code='902102938')
        self.assert_form_not_valid(country='US', state='CA', postal_code='1234567890')
        switch.active = False
        switch.save()

    def test_countries_sorting(self):
        """ Verify the country choices are sorted by country name. """
        data = self._generate_data()
        form = PaymentForm(user=self.user, data=data, request=self.request)
        expected = sorted([(country.alpha_2, country.name) for country in pycountry.countries], key=lambda x: x[1])
        actual = list(form.fields['country'].choices)
        actual.pop(0)   # Remove the "Choose country" placeholder
        self.assertEqual(actual, expected)

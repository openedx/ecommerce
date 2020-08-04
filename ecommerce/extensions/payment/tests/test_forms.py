

import ddt
import pycountry
from oscar.core.loading import get_model
from oscar.test import factories
from waffle.models import Switch

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.payment.forms import PaymentForm
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')


@ddt.ddt
class PaymentFormTests(TestCase):
    def setUp(self):
        super(PaymentFormTests, self).setUp()
        self.user = self.create_user()
        self.basket = create_basket(owner=self.user)

    def create_basket_and_add_product(self, product):
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(product, 1)
        return basket

    def prepare_course_seat_and_enrollment_code(self, seat_type='verified', id_verification=False):
        """Helper function that creates a new course, enables enrollment codes and creates a new
        seat and enrollment code for it.

        Args:
            seat_type (str): Seat/certification type.
            is_verification (bool): Whether or not id verification is required for the seat.
        Returns:
            The newly created course, seat and enrollment code.
        """
        course = CourseFactory(partner=self.partner)
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        self.site.siteconfiguration.enable_enrollment_codes = True
        self.site.siteconfiguration.save()
        seat = course.create_or_update_seat(seat_type, id_verification, 10, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        return course, seat, enrollment_code

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
        switch.flush()
        self.assert_form_valid(country='US', state='CA')
        self.assert_form_valid(country='US', address_line1=None)
        switch.active = False
        switch.save()
        switch.flush()
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

    def test_organization_field_in_form(self):
        """
        Verify the field 'organization' and 'purchased_for_organization' is present in the form
        when the basket has an enrollment code product.
        """
        _, __, enrollment_code = self.prepare_course_seat_and_enrollment_code()
        basket = self.create_basket_and_add_product(enrollment_code)
        self.request.basket = basket
        data = {
            'basket': basket.id,
            'first_name': 'Test',
            'last_name': 'User',
            'address_line1': '141 Portland Ave.',
            'address_line2': 'Floor 9',
            'city': 'Cambridge',
            'state': 'MA',
            'postal_code': '02139',
            'country': 'US',
        }
        form = PaymentForm(user=self.user, data=data, request=self.request)
        self.assertTrue('organization' in form.fields)
        self.assertTrue(PURCHASER_BEHALF_ATTRIBUTE in form.fields)

    def test_organization_field_not_in_form(self):
        """
        Verify the field 'organization' is not present in the form when the basket does not have an enrollment
        code product.
        """
        course = CourseFactory(partner=self.partner)
        product1 = course.create_or_update_seat("Verified", True, 0)
        basket = self.create_basket_and_add_product(product1)
        self.request.basket = basket
        data = {
            'basket': basket.id,
            'first_name': 'Test',
            'last_name': 'User',
            'address_line1': '141 Portland Ave.',
            'address_line2': 'Floor 9',
            'city': 'Cambridge',
            'state': 'MA',
            'postal_code': '02139',
            'country': 'US',
        }
        form = PaymentForm(user=self.user, data=data, request=self.request)
        self.assertFalse('organization' in form.fields)
        self.assertFalse(PURCHASER_BEHALF_ATTRIBUTE in form.fields)

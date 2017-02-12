from __future__ import unicode_literals

import logging

import pycountry
import waffle
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Div, Layout
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model

logger = logging.getLogger(__name__)

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')


def country_choices():
    """ Returns a tuple of tuples, each containing an ISO 3166 country code and the country name. """
    countries = sorted(
        [(country.alpha_2, country.name) for country in pycountry.countries],
        key=lambda x: x[1]
    )
    # Inserting a placeholder here so that the first option
    # when rendering the dropdown isn't a valid country.
    countries.insert(0, ('', '<{}>'.format(_('Choose country'))))
    return countries


def update_basket_queryset_filter(form, user):
    form.fields['basket'].queryset = form.fields['basket'].queryset.filter(owner=user, status=Basket.OPEN)


class PaymentForm(forms.Form):
    """
    Payment form with billing details.

    This form captures the data necessary to complete a payment transaction. The current field constraints pertain
    to CyberSource Silent Order POST, but should work nicely with other payment providers.
    """

    def __init__(self, user, request, *args, **kwargs):
        super(PaymentForm, self).__init__(*args, **kwargs)
        self.request = request
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Div('basket'),
            Div(
                Div('first_name'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('last_name'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('address_line1'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('address_line2'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('city'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('country'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('state'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            ),
            Div(
                Div('postal_code'),
                HTML('<p class="help-block"></p>'),
                css_class='form-item col-md-6'
            )
        )
        update_basket_queryset_filter(self, user)

        for bound_field in self:
            # https://www.w3.org/WAI/tutorials/forms/validation/#validating-required-input
            if hasattr(bound_field, 'field') and bound_field.field.required:
                # Translators: This is a string added next to the name of the required
                # fields on the payment form. For example, the first name field is
                # required, so this would read "First name (required)".
                self.fields[bound_field.name].label = _('{label} (required)').format(label=bound_field.label)
                bound_field.field.widget.attrs['required'] = 'required'

    basket = forms.ModelChoiceField(
        queryset=Basket.objects.all(),
        widget=forms.HiddenInput(),
        required=False,
        error_messages={
            'invalid_choice': _('There was a problem retrieving your basket. Refresh the page to try again.'),
        }
    )
    first_name = forms.CharField(max_length=60, label=_('First Name'))
    last_name = forms.CharField(max_length=60, label=_('Last Name'))
    address_line1 = forms.CharField(max_length=60, label=_('Address'), required=False)
    address_line2 = forms.CharField(max_length=29, required=False, label=_('Suite/Apartment Number'))
    city = forms.CharField(max_length=32, label=_('City'))
    # max_length for state field is set to default 60, if it needs to be changed,
    # the equivalent (maxlength) attribute in the basket page JS code needs to be changed too.
    state = forms.CharField(max_length=60, required=False, label=_('State/Province'))
    postal_code = forms.CharField(max_length=10, required=False, label=_('Zip/Postal Code'))
    country = forms.ChoiceField(choices=country_choices, label=_('Country'))

    def clean_basket(self):
        basket = self.cleaned_data['basket']

        if basket:
            basket.strategy = self.request.strategy
            Applicator().apply(basket, self.request.user, self.request)

        return basket

    def clean(self):
        cleaned_data = super(PaymentForm, self).clean()

        # Perform specific validation for the United States and Canada
        country = cleaned_data.get('country')
        if country in ('US', 'CA'):
            state = cleaned_data.get('state')
            address_line1 = cleaned_data.get('address_line1')

            # Add a flag for the below code that requires state while running this test
            # https://openedx.atlassian.net/browse/LEARNER-2355
            # State will still be required client side for users not in the hide location fields variation

            # Ensure that a valid 2-character state/province code is specified.
            if not waffle.switch_is_active('optional_location_fields'):
                if not state:
                    raise ValidationError({'state': _('This field is required.')})
                if not address_line1:
                    raise ValidationError({'address_line1': _('This field is required.')})

            if state:
                code = '{country}-{state}'.format(country=country, state=state)

                try:
                    # TODO: Remove the if statement once https://bitbucket.org/flyingcircus/pycountry/issues/13394/
                    # is fixed.
                    if not pycountry.subdivisions.get(code=code):
                        raise KeyError
                except KeyError:
                    msg = _('{state} is not a valid state/province in {country}.').format(state=state, country=country)
                    logger.debug(msg)
                    raise ValidationError({'state': msg})

            # Ensure the postal code is present, and limited to 9 characters
            postal_code = cleaned_data.get('postal_code')

            # Add a flag for the below code that requires postal code while running this test
            # https://openedx.atlassian.net/browse/LEARNER-2355
            # I could require it client side, but am not because it is not currently marked as required for the user

            if not waffle.switch_is_active('optional_location_fields'):
                if not postal_code:
                    raise ValidationError({'postal_code': _('This field is required.')})

            if postal_code and len(postal_code) > 9:
                raise ValidationError(
                    {
                        'postal_code': _(
                            'Postal codes for the U.S. and Canada are limited to nine (9) characters.')
                    })

        return cleaned_data


class StripePaymentForm(forms.Form):
    """
    Payment form for the Stripe payment processor.

    This form differs drastically from `PaymentForm` because we can use the Stripe API to pull the billing address
    from the token. This information is encoded in the token because we explicitly include the HTML form data in our
    token creation request to Stripe.
    """
    stripe_token = forms.CharField(widget=forms.HiddenInput(), required=True)
    basket = forms.ModelChoiceField(
        queryset=Basket.objects.all(),
        widget=forms.HiddenInput(),
        error_messages={
            'invalid_choice': _('There was a problem retrieving your basket. Refresh the page to try again.'),
        }
    )

    def __init__(self, user, request, *args, **kwargs):
        super(StripePaymentForm, self).__init__(*args, **kwargs)
        self.request = request
        update_basket_queryset_filter(self, user)

    def clean_basket(self):
        basket = self.cleaned_data['basket']

        if basket:
            basket.strategy = self.request.strategy
            Applicator().apply(basket, self.request.user, self.request)

        return basket

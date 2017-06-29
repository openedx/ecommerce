from __future__ import unicode_literals

import logging

import pycountry
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Div, Layout
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
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


class PaymentForm(forms.Form):
    """
    Payment form with billing details.

    This form captures the data necessary to complete a payment transaction. The current field constraints pertain
    to CyberSource Silent Order POST, but should work nicely with other payment providers.
    """

    def __init__(self, user, *args, **kwargs):
        super(PaymentForm, self).__init__(*args, **kwargs)
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
        self.fields['basket'].queryset = self.fields['basket'].queryset.filter(owner=user)
        for bound_field in self:
            # https://www.w3.org/WAI/tutorials/forms/validation/#validating-required-input
            if hasattr(bound_field, 'field') and bound_field.field.required:
                # Translators: This is a string added next to the name of the required
                # fields on the payment form. For example, the first name field is
                # required, so this would read "First name (required)".
                self.fields[bound_field.name].label = _('{label} (required)').format(label=bound_field.label)
                bound_field.field.widget.attrs['required'] = 'required'

    basket = forms.ModelChoiceField(queryset=Basket.objects.all(), widget=forms.HiddenInput(), required=False)
    first_name = forms.CharField(max_length=60, label=_('First Name'))
    last_name = forms.CharField(max_length=60, label=_('Last Name'))
    address_line1 = forms.CharField(max_length=60, label=_('Address'))
    address_line2 = forms.CharField(max_length=29, required=False, label=_('Suite/Apartment Number'))
    city = forms.CharField(max_length=32, label=_('City'))
    # max_length for state field is set to default 60, if it needs to be changed,
    # the equivalent (maxlength) attribute in the basket page JS code needs to be changed too.
    state = forms.CharField(max_length=60, required=False, label=_('State/Province'))
    postal_code = forms.CharField(max_length=10, required=False, label=_('Zip/Postal Code'))
    country = forms.ChoiceField(choices=country_choices, label=_('Country'))

    def clean(self):
        cleaned_data = super(PaymentForm, self).clean()

        # Perform specific validation for the United States and Canada
        country = cleaned_data.get('country')
        if country in ('US', 'CA'):
            state = cleaned_data.get('state')

            # Ensure that a valid 2-character state/province code is specified.
            if not state:
                raise ValidationError({'state': _('This field is required.')})

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
            if not postal_code:
                raise ValidationError({'postal_code': _('This field is required.')})

            if len(postal_code) > 9:
                raise ValidationError(
                    {'postal_code': _(
                        'Postal codes for the U.S. and Canada are limited to nine (9) characters.')})

        return cleaned_data

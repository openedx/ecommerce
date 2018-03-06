# -*- coding: utf-8 -*-
from django import forms
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

#TODO: replace with digital_book constants
from ecommerce.programs.constants import BENEFIT_TYPE_CHOICES, BENEFIT_MAP
from ecommerce.programs.custom import class_path, create_condition

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')


class DigitalBookOfferForm(forms.ModelForm):
    digital_book_bundle_uuid = forms.UUIDField(
        required=True,
        label=_('Digital Book Bundle UUID')
    )
    benefit_type = forms.ChoiceField(
        choices=BENEFIT_TYPE_CHOICES,
        label=_('Discount Type')
    )
    benefit_value = forms.DecimalField(
        required=True,
        decimal_places=2,
        max_digits=12,
        min_value=0,
        label=_('Discount Value')
    )

    class Meta(object):
        model = ConditionalOffer
        fields = ['digital_book_bundle_uuid', 'start_datetime', 'end_datetime', 'benefit_type', 'benefit_value']
        help_texts = {
            'end_datetime': ''
        }
        labels = {
            'start_datetime': _('Start Date'),
            'end_datetime': _('End Date'),
        }

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=None, empty_permitted=False, instance=None, request=None):
        initial = initial or {}
        self.request = request
        if instance:
            initial.update({
                'digital_book_bundle': instance.condition.digital_book_bundle_uuid,
                'benefit_type': instance.benefit.proxy().benefit_class_type,
                'benefit_value': instance.benefit.value,
            })
        super(DigitalBookOfferForm, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix,
                                                   empty_permitted, instance)
        date_ui_class = {'class': 'add-pikaday'}
        self.fields['start_datetime'].widget.attrs.update(date_ui_class)
        self.fields['end_datetime'].widget.attrs.update(date_ui_class)

    def clean(self):
        cleaned_data = super(DigitalBookOfferForm, self).clean()

        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')
        digital_book_bundle_uuid = cleaned_data.get('digital_book_bundle_uuid')

        if not self.instance.pk and digital_book_bundle_uuid:
            digital_book_offer_exists = ConditionalOffer.objects.filter(
                offer_type=ConditionalOffer.SITE,
                condition__digital_book_offer_uuid=digital_book_bundle_uuid
            ).exists()

            if digital_book_offer_exists:
                self.add_error('digital_book_bundle_uuid', _('An offer already exists for this digital book bundle'))

        if cleaned_data['benefit_type'] == Benefit.PERCENTAGE and cleaned_data.get('benefit_value') > 100:
            self.add_error('benefit_value', _('Percentage discounts cannot be greater than 100%.'))

        if end_datetime and not start_datetime:
            self.add_error('start_datetime', _('A start date must be specified when specifying an end date'))

        if start_datetime and end_datetime and start_datetime > end_datetime:
            self.add_error('start_datetime', _('The start date must occur before the end date'))

        return cleaned_data

    def save(self, commit=True):
        digital_book_bundle_uuid = self.cleaned_data['digital_book_bundle_uuid']
        site = self.request.site

        #TODO: talk to discovery service to query the digital book bundle
        #TODO: generate offer name from query

        offer_name = 'Digital Book Offer {uuid}'.format(
            uuid=digital_book_bundle_uuid
        )

        # Truncate offer_names down to 128 characters, as Oscar's AbstractConditionalOffer name is max_length 128
        offer_name = (offer_name[:125] + '...') if len(offer_name) > 128 else offer_name  # pylint: disable=unsubscriptable-object

        self.instance.name = offer_name
        self.instance.status = ConditionalOffer.OPEN
        self.instance.offer_type = ConditionalOffer.SITE
        self.instance.max_basket_applications = 1
        self.instance.site = site

        if commit:
            benefit = getattr(self.instance, 'benefit', Benefit)
            benefit.proxy_class = class_path(BENEFIT_MAP[self.cleaned_data['benefit_type']])
            benefit.value = self.cleaned_data['benefit_value']
            benefit.save()
            self.instance.benefit = benefit

            if hasattr(self.instance, 'condition'):
                self.instance.condition.digital_book_bundle_uuid = digital_book_bundle_uuid
                self.instance.condition.save()
            else:
                self.instance.condition = create_condition(DigitalBookBundleCondition, digital_book_bundle_uuid=digital_book_bundle_uuid)

            return super(DigitalBookOfferForm, self).save(commit)


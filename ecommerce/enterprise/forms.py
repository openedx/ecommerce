# -*- coding: utf-8 -*-
# TODO: Refactor this to consolidate it with `ecommerce.programs.forms`.
from django import forms
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.constants import BENEFIT_MAP, BENEFIT_TYPE_CHOICES
from ecommerce.enterprise.utils import get_enterprise_customer
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE
from ecommerce.programs.custom import class_path, create_condition

Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Range = get_model('offer', 'Range')


class EnterpriseOfferForm(forms.ModelForm):
    enterprise_customer_uuid = forms.UUIDField(required=True, label=_('Enterprise Customer UUID'))
    enterprise_customer_catalog_uuid = forms.UUIDField(required=False, label=_('Enterprise Customer Catalog UUID'))
    benefit_type = forms.ChoiceField(choices=BENEFIT_TYPE_CHOICES, label=_('Discount Type'))
    benefit_value = forms.DecimalField(
        required=True, decimal_places=2, max_digits=12, min_value=0, label=_('Discount Value')
    )

    class Meta(object):
        model = ConditionalOffer
        fields = [
            'enterprise_customer_uuid', 'enterprise_customer_catalog_uuid', 'start_datetime', 'end_datetime',
            'benefit_type', 'benefit_value'
        ]
        help_texts = {
            'end_datetime': '',
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
                'enterprise_customer_uuid': instance.condition.enterprise_customer_uuid,
                'enterprise_customer_catalog_uuid': instance.condition.enterprise_customer_catalog_uuid,
                'benefit_type': instance.benefit.proxy().benefit_class_type,
                'benefit_value': instance.benefit.value,
            })
        super(EnterpriseOfferForm, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix,
                                                  empty_permitted, instance)

        date_ui_class = {'class': 'add-pikaday'}
        self.fields['start_datetime'].widget.attrs.update(date_ui_class)
        self.fields['end_datetime'].widget.attrs.update(date_ui_class)

    def clean(self):
        cleaned_data = super(EnterpriseOfferForm, self).clean()

        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')
        enterprise_customer_uuid = cleaned_data.get('enterprise_customer_uuid')
        enterprise_customer_catalog_uuid = cleaned_data.get('enterprise_customer_catalog_uuid')

        if not self.instance.pk and enterprise_customer_uuid and enterprise_customer_catalog_uuid:
            enterprise_offer_exists = ConditionalOffer.objects.filter(
                offer_type=ConditionalOffer.SITE,
                condition__enterprise_customer_uuid=enterprise_customer_uuid,
                condition__enterprise_customer_catalog_uuid=enterprise_customer_catalog_uuid,
            ).exists()

            if enterprise_offer_exists:
                for field in ['enterprise_customer_uuid', 'enterprise_customer_catalog_uuid']:
                    self.add_error(field, _('An offer already exists for this Enterprise & Catalog combination.'))

        if cleaned_data['benefit_type'] == Benefit.PERCENTAGE and cleaned_data.get('benefit_value') > 100:
            self.add_error('benefit_value', _('Percentage discounts cannot be greater than 100%.'))

        if end_datetime and not start_datetime:
            self.add_error('start_datetime', _('A start date must be specified when specifying an end date.'))

        if start_datetime and end_datetime and start_datetime > end_datetime:
            self.add_error('start_datetime', _('The start date must occur before the end date.'))

        return cleaned_data

    def save(self, commit=True):
        enterprise_customer_uuid = self.cleaned_data['enterprise_customer_uuid']
        enterprise_customer_catalog_uuid = self.cleaned_data['enterprise_customer_catalog_uuid']
        site = self.request.site

        enterprise_customer = get_enterprise_customer(site, enterprise_customer_uuid)
        enterprise_customer_name = enterprise_customer['name']

        self.instance.name = _(u'Discount provided by {enterprise_customer_name}.'.format(
            enterprise_customer_name=enterprise_customer_name
        ))
        self.instance.status = ConditionalOffer.OPEN
        self.instance.offer_type = ConditionalOffer.SITE
        self.instance.max_basket_applications = 1
        self.instance.site = site
        self.instance.priority = OFFER_PRIORITY_ENTERPRISE

        if commit:
            benefit = getattr(self.instance, 'benefit', Benefit())
            benefit.proxy_class = class_path(BENEFIT_MAP[self.cleaned_data['benefit_type']])
            benefit.value = self.cleaned_data['benefit_value']
            benefit.save()
            self.instance.benefit = benefit

            if hasattr(self.instance, 'condition'):
                self.instance.condition.enterprise_customer_uuid = enterprise_customer_uuid
                self.instance.condition.enterprise_customer_name = enterprise_customer_name
                self.instance.condition.enterprise_customer_catalog_uuid = enterprise_customer_catalog_uuid
                self.instance.condition.save()
            else:
                self.instance.condition = create_condition(
                    EnterpriseCustomerCondition,
                    enterprise_customer_uuid=enterprise_customer_uuid,
                    enterprise_customer_name=enterprise_customer_name,
                    enterprise_customer_catalog_uuid=enterprise_customer_catalog_uuid,
                )

        return super(EnterpriseOfferForm, self).save(commit)

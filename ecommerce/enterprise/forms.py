# -*- coding: utf-8 -*-
# TODO: Refactor this to consolidate it with `ecommerce.programs.forms`.
from __future__ import absolute_import

from django import forms
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.enterprise.benefits import BENEFIT_MAP, BENEFIT_TYPE_CHOICES
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.utils import get_enterprise_customer
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.programs.custom import class_path, create_condition

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Range = get_model('offer', 'Range')


class EnterpriseOfferForm(forms.ModelForm):
    enterprise_customer_uuid = forms.UUIDField(required=True, label=_('Enterprise Customer UUID'))
    enterprise_customer_catalog_uuid = forms.UUIDField(required=False, label=_('Enterprise Customer Catalog UUID'))
    benefit_type = forms.ChoiceField(choices=BENEFIT_TYPE_CHOICES, label=_('Discount Type'))
    benefit_value = forms.DecimalField(
        required=True, decimal_places=2, max_digits=12, min_value=0, label=_('Discount Value')
    )
    contract_discount_type = forms.ChoiceField(
        required=False, choices=EnterpriseContractMetadata.DISCOUNT_TYPE_CHOICES, label=_('Contract Discount Type')
    )
    contract_discount_value = forms.DecimalField(
        required=False, decimal_places=5, max_digits=15, min_value=0, label=_('Contract Discount')
    )
    prepaid_invoice_amount = forms.DecimalField(
        required=False, decimal_places=5, max_digits=15, min_value=0, label=_('Prepaid Invoice Amount')
    )

    class Meta(object):
        model = ConditionalOffer
        fields = [
            'enterprise_customer_uuid', 'enterprise_customer_catalog_uuid', 'start_datetime', 'end_datetime',
            'benefit_type', 'benefit_value', 'contract_discount_type', 'contract_discount_value', 'prepaid_invoice_amount',
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
        contract_discount_type = cleaned_data.get('contract_discount_type')
        contract_discount_value = cleaned_data.get('contract_discount_value')
        prepaid_invoice_amount = cleaned_data.get('prepaid_invoice_amount')

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

        if contract_discount_value is not None:
            if contract_discount_type == EnterpriseContractMetadata.PERCENTAGE and contract_discount_value > 100:
                self.add_error('contract_discount_value', _('Percentage discounts cannot be greater than 100%.'))
            elif contract_discount_type == EnterpriseContractMetadata.FIXED:
                before_decimal, __, after_decimal = str(contract_discount_value).partition('.')
                if len(before_decimal) > 10:
                    self.add_error('contract_discount_value', _(
                        'More than 10 digits before the decimal '
                        'not allowed for absolute value.'
                    ))
                if len(after_decimal) > 2:
                    self.add_error('contract_discount_value', _(
                        'More than 2 digits after the decimal '
                        'not allowed for absolute value.'
                    ))
                if prepaid_invoice_amount is None:
                    self.add_error('prepaid_invoice_amount', _(
                        'This field is required when contract '
                        'discount type is absolute.'
                    ))

        return cleaned_data

    def save(self, commit=True):
        enterprise_customer_uuid = self.cleaned_data['enterprise_customer_uuid']
        enterprise_customer_catalog_uuid = self.cleaned_data['enterprise_customer_catalog_uuid']
        site = self.request.site

        contract_discount_value = self.cleaned_data['contract_discount_value']
        contract_discount_type = self.cleaned_data['contract_discount_type']
        prepaid_invoice_amount = self.cleaned_data['prepaid_invoice_amount']

        enterprise_customer = get_enterprise_customer(site, enterprise_customer_uuid)
        enterprise_customer_name = enterprise_customer['name']

        # Note: the actual name is not displayed like this in the template, so it's safe to use the UUID here.
        # And in fact we have to, because otherwise we face integrity errors since Oscar forces this name to be unique.
        # Truncate 'enterprise_customer_name' to 48 characters so that our complete name with
        # format 'Discount of type {site} provided by {enterprise_name} for {catalog_uuid}. does
        # not exceed the limit of 128 characters for Oscar's 'AbstractConditionalOffer' name.
        offer_name = _(u'Discount of type {} provided by {} for {}.'.format(
            ConditionalOffer.SITE,
            enterprise_customer_name[:48],  # pylint: disable=unsubscriptable-object,
            enterprise_customer_catalog_uuid
        ))

        self.instance.name = offer_name
        self.instance.status = ConditionalOffer.OPEN
        self.instance.offer_type = ConditionalOffer.SITE
        self.instance.max_basket_applications = 1
        self.instance.partner = site.siteconfiguration.partner
        self.instance.priority = OFFER_PRIORITY_ENTERPRISE


        print("\n\n\n\n\n\n\n\n------------------------")
        if commit:
            ecm = self.instance.enterprise_contract_metadata
            print(ecm)
            if ecm is None:
                ecm = EnterpriseContractMetadata()
            print(ecm)
            ecm.discount_value = contract_discount_value
            ecm.discount_type = contract_discount_type
            ecm.amount_paid = prepaid_invoice_amount
            ecm.clean()
            ecm.save()
            self.instance.enterprise_contract_metadata = ecm
            print(self.instance.enterprise_contract_metadata)
            print(self.instance.enterprise_contract_metadata.discount_value)
            print(self.instance.enterprise_contract_metadata.discount_type)
            print(self.instance.enterprise_contract_metadata.amount_paid)

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

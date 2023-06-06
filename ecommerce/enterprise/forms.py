# -*- coding: utf-8 -*-
# TODO: Refactor this to consolidate it with `ecommerce.programs.forms`.


import decimal
import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Max, Sum
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.enterprise.benefits import BENEFIT_MAP, BENEFIT_TYPE_CHOICES
from ecommerce.enterprise.conditions import EnterpriseCustomerCondition
from ecommerce.enterprise.constants import (
    ENTERPRISE_SALES_FORCE_ID_REGEX,
    ENTERPRISE_SALESFORCE_OPPORTUNITY_LINE_ITEM_REGEX
)
from ecommerce.enterprise.utils import convert_comma_separated_string_to_list, get_enterprise_customer
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.offer.models import OFFER_PRIORITY_ENTERPRISE
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.refund.status import REFUND
from ecommerce.programs.custom import class_path, create_condition

Benefit = get_model('offer', 'Benefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Order = get_model('order', 'Order')
OrderDiscount = get_model('order', 'OrderDiscount')
Range = get_model('offer', 'Range')
Refund = get_model('refund', 'Refund')


class EnterpriseOfferForm(forms.ModelForm):
    enterprise_customer_uuid = forms.UUIDField(required=True, label=_('Enterprise Customer UUID'))
    enterprise_customer_catalog_uuid = forms.UUIDField(required=False, label=_('Enterprise Customer Catalog UUID'))
    benefit_type = forms.ChoiceField(choices=BENEFIT_TYPE_CHOICES, label=_('Discount Type'))
    benefit_value = forms.DecimalField(
        required=True, decimal_places=2, max_digits=12, min_value=0, label=_('Discount Value')
    )
    contract_discount_type = forms.ChoiceField(
        required=True, choices=EnterpriseContractMetadata.DISCOUNT_TYPE_CHOICES, label=_('Contract Discount Type')
    )
    contract_discount_value = forms.DecimalField(
        required=True, decimal_places=5, max_digits=15, min_value=0, label=_('Contract Discount')
    )
    prepaid_invoice_amount = forms.DecimalField(
        required=False, decimal_places=5, max_digits=15, min_value=0, label=_('Prepaid Invoice Amount')
    )
    sales_force_id = forms.CharField(max_length=30, required=False, label=_('Salesforce Opportunity ID'))
    salesforce_opportunity_line_item = forms.CharField(
        max_length=30, required=False, label=_('Salesforce Opportunity Line Item'))
    emails_for_usage_alert = forms.CharField(
        required=False,
        label=_("Emails Addresses"),
        help_text=_("Comma separated emails which will receive the offer usage alerts")
    )
    usage_email_frequency = forms.ChoiceField(
        required=True,
        choices=ConditionalOffer.USAGE_EMAIL_FREQUENCY_CHOICES,
        label=_("Frequency for offer usage emails")
    )

    class Meta:
        model = ConditionalOffer
        fields = [
            'enterprise_customer_uuid', 'enterprise_customer_catalog_uuid', 'start_datetime',
            'end_datetime', 'benefit_type', 'benefit_value', 'contract_discount_type',
            'contract_discount_value', 'prepaid_invoice_amount', 'sales_force_id',
            'salesforce_opportunity_line_item',
            'max_global_applications', 'max_discount', 'max_user_applications', 'max_user_discount',
            'emails_for_usage_alert', 'usage_email_frequency'
        ]
        help_texts = {
            'end_datetime': '',
            'max_global_applications': _('The maximum number of enrollments that can redeem this offer.'),
            'max_discount': _('The maximum USD dollar amount that can be redeemed by this offer.'),
            'max_user_applications': _('The maximum number of enrollments, by a user, that can redeem this offer.'),
            'max_user_discount': _('The maximum USD dollar amount that can be redeemed using this offer by a user.'),
        }
        labels = {
            'start_datetime': _('Start Date'),
            'end_datetime': _('End Date'),
            'max_global_applications': _('Enrollment Limit'),
            'max_discount': _('Bookings Limit'),
            'max_user_applications': _('Per User Enrollment Limit'),
            'max_user_discount': _('Per User Bookings Limit'),
        }

    def _prep_contract_metadata(self, enterprise_contract_metadata):
        """
        Reconciles the way we store the data with how we serve up the form.

        Reduces trailing decimals for Absolute contract_discount_value case.
        Sets all contract metadata fields for preexisting offers that do not
        have a contract metadata object existing.

        Returns a tuple: discount_type, discount_value, and invoice_amount
        """
        if enterprise_contract_metadata is None:
            return (None, None, None)

        contract_discount_type = enterprise_contract_metadata.discount_type
        prepaid_invoice_amount = enterprise_contract_metadata.amount_paid

        contract_discount_value = enterprise_contract_metadata.discount_value
        before_decimal, dec, after_decimal = str(contract_discount_value).partition('.')
        if contract_discount_type == EnterpriseContractMetadata.FIXED and len(after_decimal) > 2:
            after_decimal = after_decimal[0:2]
            contract_discount_value = before_decimal + dec + after_decimal

        return (contract_discount_type, contract_discount_value, prepaid_invoice_amount)

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=None, empty_permitted=False, instance=None, request=None):
        initial = initial or {}
        self.request = request
        if instance:
            contract_discount_type, contract_discount_value, prepaid_invoice_amount = self._prep_contract_metadata(
                instance.enterprise_contract_metadata
            )
            initial.update({
                'enterprise_customer_uuid': instance.condition.enterprise_customer_uuid,
                'enterprise_customer_catalog_uuid': instance.condition.enterprise_customer_catalog_uuid,
                'benefit_type': instance.benefit.proxy().benefit_class_type,
                'benefit_value': instance.benefit.value,
                'contract_discount_type': contract_discount_type,
                'contract_discount_value': contract_discount_value,
                'prepaid_invoice_amount': prepaid_invoice_amount,
            })
        super(EnterpriseOfferForm, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix,
                                                  empty_permitted, instance)

        date_ui_class = {'class': 'add-pikaday'}
        self.fields['start_datetime'].widget.attrs.update(date_ui_class)
        self.fields['end_datetime'].widget.attrs.update(date_ui_class)
        # set the min attribute on input widget to enforce minimum value validation at frontend
        self.fields['max_discount'].widget.attrs.update({'min': 0})
        self.fields['max_user_discount'].widget.attrs.update({'min': 0})

    def clean_max_global_applications(self):
        # validate against when decreasing the existing value
        if self.instance.pk and self.instance.max_global_applications:
            new_max_global_applications = self.cleaned_data.get('max_global_applications') or 0
            if new_max_global_applications < self.instance.num_applications:
                self.add_error(
                    'max_global_applications',
                    _(
                        'Ensure new value must be greater than or equal to consumed({offer_enrollments}) value.'
                    ).format(
                        offer_enrollments=self.instance.num_applications
                    )
                )

        return self.cleaned_data.get('max_global_applications')

    def clean_sales_force_id(self):
        # validate sales_force_id format
        sales_force_id = self.cleaned_data.get('sales_force_id')
        if sales_force_id and not re.match(ENTERPRISE_SALES_FORCE_ID_REGEX, sales_force_id):
            self.add_error(
                'sales_force_id',
                _('Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006.')
            )
        return self.cleaned_data.get('sales_force_id')

    def clean_salesforce_opportunity_line_item(self):
        # validate salesforce_opportunity_line_item format
        salesforce_opportunity_line_item = self.cleaned_data.get('salesforce_opportunity_line_item')
        if not re.match(ENTERPRISE_SALESFORCE_OPPORTUNITY_LINE_ITEM_REGEX, salesforce_opportunity_line_item):
            self.add_error(
                'salesforce_opportunity_line_item',
                _('The Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number.')
            )
        return self.cleaned_data.get('salesforce_opportunity_line_item')

    def clean_max_discount(self):
        max_discount = self.cleaned_data.get('max_discount')
        # validate against non-decimal and negative values
        if max_discount is not None and (isinstance(max_discount, decimal.Decimal) and max_discount < 0):
            self.add_error('max_discount', _('Ensure this value is greater than or equal to 0.'))
        elif self.instance.pk and self.instance.max_discount:  # validate against when decrease the existing value
            new_max_discount = max_discount or 0
            if new_max_discount < self.instance.total_discount:
                self.add_error(
                    'max_discount',
                    _(
                        'Ensure new value must be greater than or equal to consumed({consumed_discount:.2f}) value.'
                    ).format(
                        consumed_discount=self.instance.total_discount
                    )
                )

        return max_discount

    def _get_refunded_order_ids(self, offer_id):
        # Get all refunded order ids belonging to the offer and with status = 'COMPLETE'
        return list(Refund.objects.filter(
            order__discounts__offer_id=offer_id,
            status=REFUND.COMPLETE
        ).values_list('order_id', flat=True))

    def clean_max_user_applications(self):
        # validate against when decreasing the existing value
        if self.instance.pk and self.instance.max_user_applications:
            new_max_user_applications = self.cleaned_data.get('max_user_applications') or 0
            refunded_order_ids = self._get_refunded_order_ids(self.instance.id)
            max_order_count_any_user = OrderDiscount.objects.filter(
                offer_id=self.instance.id).select_related('order').filter(
                    order__status=ORDER.COMPLETE).exclude(order_id__in=refunded_order_ids).values(
                        'order__user_id').order_by('order__user_id').annotate(
                            count=Count('order__id')).aggregate(Max('count'))['count__max'] or 0
            if new_max_user_applications < max_order_count_any_user:
                self.add_error(
                    'max_user_applications',
                    _(
                        'Ensure new value must be greater than or equal to consumed({offer_enrollments}) value.'
                    ).format(
                        offer_enrollments=max_order_count_any_user
                    )
                )

        return self.cleaned_data.get('max_user_applications')

    def clean_max_user_discount(self):
        max_user_discount = self.cleaned_data.get('max_user_discount')
        # validate against non-decimal and negative values
        if max_user_discount is not None and (isinstance(max_user_discount, decimal.Decimal) and max_user_discount < 0):
            self.add_error('max_user_discount', _('Ensure this value is greater than or equal to 0.'))
        elif self.instance.pk:  # validate against when decrease the existing value
            new_max_user_discount = max_user_discount or 0
            # we only need to do validation if new max_user_discount value is less then existing value
            if self.instance.max_user_discount and new_max_user_discount < self.instance.max_user_discount:
                # calculates the maximum user discount consumed by any user out of the user bookings limit
                refunded_order_ids = self._get_refunded_order_ids(self.instance.id)
                max_discount_used_any_user = OrderDiscount.objects.filter(offer_id=self.instance.id).select_related(
                    'order').filter(order__status=ORDER.COMPLETE).exclude(
                        order_id__in=refunded_order_ids).values('order__user_id').order_by('order__user_id').annotate(
                            user_discount_sum=Sum('amount')).aggregate(
                                Max('user_discount_sum'))['user_discount_sum__max'] or 0
                if new_max_user_discount < max_discount_used_any_user:
                    self.add_error(
                        'max_user_discount',
                        _(
                            'Ensure new value must be greater than or equal to consumed({consumed_discount:.2f}) value.'
                        ).format(
                            consumed_discount=max_discount_used_any_user
                        )
                    )

        return max_user_discount

    def clean_emails_for_usage_alert(self):
        emails_for_usage_alert = self.cleaned_data.get('emails_for_usage_alert')
        emails = convert_comma_separated_string_to_list(emails_for_usage_alert)
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                self.add_error(
                    'emails_for_usage_alert',
                    _('Given email address {email} is not a valid email.'.format(email=email))
                )
                break
        return emails_for_usage_alert

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

        if contract_discount_type == EnterpriseContractMetadata.PERCENTAGE and contract_discount_value > 100:
            self.add_error('contract_discount_value', _('Percentage discounts cannot be greater than 100%.'))
        elif contract_discount_type == EnterpriseContractMetadata.FIXED:
            __, ___, after_decimal = str(contract_discount_value).partition('.')
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
        sales_force_id = self.cleaned_data['sales_force_id']
        salesforce_opportunity_line_item = self.cleaned_data['salesforce_opportunity_line_item']
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
        self.instance.sales_force_id = sales_force_id
        self.instance.salesforce_opportunity_line_item = salesforce_opportunity_line_item

        self.instance.max_global_applications = self.cleaned_data.get('max_global_applications')
        self.instance.max_discount = self.cleaned_data.get('max_discount')
        self.instance.max_user_applications = self.cleaned_data.get('max_user_applications')
        self.instance.max_user_discount = self.cleaned_data.get('max_user_discount')
        self.instance.emails_for_usage_alert = self.cleaned_data.get('emails_for_usage_alert')

        if commit:
            ecm = self.instance.enterprise_contract_metadata
            if ecm is None:
                ecm = EnterpriseContractMetadata()
            ecm.discount_value = contract_discount_value
            ecm.discount_type = contract_discount_type
            ecm.amount_paid = prepaid_invoice_amount
            ecm.clean()
            ecm.save()
            self.instance.enterprise_contract_metadata = ecm

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

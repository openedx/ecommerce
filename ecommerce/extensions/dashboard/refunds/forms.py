from django import forms
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

Refund = get_model('refund', 'Refund')


class RefundSearchForm(forms.Form):
    id = forms.IntegerField(required=False, label=_('Refund ID'))
    status_choices = (('', '---------'),) + tuple([(status, status) for status in Refund.all_statuses()])
    status = forms.ChoiceField(choices=status_choices, label=_("Status"), required=False)

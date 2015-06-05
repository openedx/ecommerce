from django import forms
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.extensions.refund.status import REFUND


Refund = get_model('refund', 'Refund')


class RefundSearchForm(forms.Form):
    id = forms.IntegerField(required=False, label=_('Refund ID'))
    status_choices = tuple([(status, status) for status in Refund.all_statuses()])
    status = forms.MultipleChoiceField(choices=status_choices, label=_("Status"), required=False)

    def clean(self):
        cleaned_data = super(RefundSearchForm, self).clean()

        if not cleaned_data.get('status'):
            # If no statuses are specified, default to displaying all those refunds requiring action.
            cleaned_data['status'] = list(set(Refund.all_statuses()) - set((REFUND.COMPLETE, REFUND.DENIED)))

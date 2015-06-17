from django import forms
from django.utils.translation import ugettext_lazy as _
from oscar.apps.dashboard.orders.forms import OrderSearchForm as CoreOrderSearchForm


class OrderSearchForm(CoreOrderSearchForm):
    username = forms.CharField(required=False, label=_("Username"))

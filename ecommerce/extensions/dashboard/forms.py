

from django import forms
from django.utils.translation import ugettext_lazy as _


class UserFormMixin(forms.Form):
    """ Mixin for user field filtering. """
    username = forms.CharField(required=False, label=_("Username"))
    email = forms.CharField(required=False, label=_("Email"))

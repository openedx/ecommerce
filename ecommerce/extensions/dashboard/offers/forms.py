

from django.contrib.sites.models import Site
from django.forms import ModelChoiceField
from oscar.apps.dashboard.offers.forms import MetaDataForm as CoreMetaDataForm
from oscar.core.loading import get_model


class MetaDataForm(CoreMetaDataForm):
    site = ModelChoiceField(queryset=Site.objects.all(), required=True)

    class Meta:
        model = get_model('offer', 'ConditionalOffer')
        fields = ('name', 'description', 'site')

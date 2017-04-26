from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _


@python_2_unicode_compatible
class Program(models.Model):
    uuid = models.CharField(max_length=255, primary_key=True)
    offer = models.OneToOneField('offer.ConditionalOffer', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    start_datetime = models.DateTimeField(
        help_text=_('Start date/time for the program discount.')
    )
    end_datetime = models.DateTimeField(
        help_text=_('End date/time for the program discount.')
    )
    last_edited_datetime = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

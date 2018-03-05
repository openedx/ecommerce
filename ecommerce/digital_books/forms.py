# -*- coding: utf-8 -*-
from django import forms
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

#TODO: replace with digital_book constants
from ecommerce.programs.constants import BENEFIT_TYPE_CHOICES

ConditionalOffer = get_model('offer', 'ConditionalOffer')

class DigitalBookOfferForm(forms.ModelForm):
    #TODO: replace book_key and course_key with generic bundle object
    #TODO: replace w/ book_uuid
    book_key = forms.CharField(max_length=200)
    #TODO: replace w/ foriegn key to course table
    course_key = forms.CharField(max_length=200)
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
        fields = ['book_key', 'course_key', 'start_datetime', 'end_datetime', 'benefit_type', 'benefit_value']
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
                'book_key': instance.book_key,
                'course_key': instance.course_key,
                'benefit_type': instance.benefit.proxy().benefit_class_type,
                'benefit_value': instance.benefit.value,
            })
        super(DigitalBookOfferForm, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix,
                                                   empty_permitted, instance)
        date_ui_class = {'class': 'add-pikaday'}
        self.fields['start_datetime'].widget.attrs.update(date_ui_class)
        self.fields['end_datetime'].widget.attrs.update(date_ui_class)


    #TODO: clean

    #TODO: save
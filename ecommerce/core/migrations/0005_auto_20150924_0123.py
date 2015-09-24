# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def make_switch(apps, schema_editor):
    """ Create, and activate, the publish_course_modes_to_lms if it does not already exist. """
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='publish_course_modes_to_lms', defaults={'active': True})


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_auto_20150915_1023'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(make_switch)
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

switches = (
    ('publish_course_modes_to_lms', True),
    ('async_order_fulfillment', False),
)


def add_switches(apps, schema_editor):
    Switch = apps.get_model('waffle', 'Switch')
    for name, active in switches:
        Switch.objects.get_or_create(name=name, defaults={'active': active})


def remove_switches(apps, schema_editor):
    Switch = apps.get_model('waffle', 'Switch')
    for name, __ in switches:
        Switch.objects.filter(name=name).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_auto_20150915_1023'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            code=add_switches,
            reverse_code=remove_switches,
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models, migrations

from ecommerce.extensions.partner.models import Partner


def create_default_partner(apps, schema_editor):
    Partner.objects.create(
        name='edX default',
        short_code='edX'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
    ]

    operations = [
        migrations.RunPython(create_default_partner)
    ]

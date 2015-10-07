# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucher',
            name='course_id',
            field=models.CharField(max_length=255, verbose_name='Course ID', blank=True),
        ),
    ]

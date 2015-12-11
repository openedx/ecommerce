# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('refund', '0001_squashed_0002_auto_20150515_2220'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='refund',
            index_together=set([('modified', 'created')]),
        ),
        migrations.AlterIndexTogether(
            name='refundline',
            index_together=set([('modified', 'created')]),
        ),
    ]

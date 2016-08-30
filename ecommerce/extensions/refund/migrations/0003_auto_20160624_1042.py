# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('refund', '0002_auto_20151214_1017'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalrefund',
            name='status',
            field=models.CharField(max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Pending With Revocation', b'Pending With Revocation'), (b'Pending Without Revocation', b'Pending Without Revocation'), (b'Payment Refund Error', b'Payment Refund Error'), (b'Payment Refunded', b'Payment Refunded'), (b'Revocation Error', b'Revocation Error'), (b'Complete', b'Complete')]),
        ),
        migrations.AlterField(
            model_name='refund',
            name='status',
            field=models.CharField(max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Pending With Revocation', b'Pending With Revocation'), (b'Pending Without Revocation', b'Pending Without Revocation'), (b'Payment Refund Error', b'Payment Refund Error'), (b'Payment Refunded', b'Payment Refunded'), (b'Revocation Error', b'Revocation Error'), (b'Complete', b'Complete')]),
        ),
    ]

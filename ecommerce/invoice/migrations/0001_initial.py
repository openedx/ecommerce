# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_client'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('invoice_number', models.CharField(max_length=20)),
                ('order_number', models.CharField(max_length=20)),
                ('state', models.CharField(default=b'Not Paid', max_length=10, choices=[(b'Not Paid', b'Not Paid'), (b'Paid', b'Paid')])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('total', models.DecimalField(max_digits=19, decimal_places=2)),
                ('purchase_order_number', models.CharField(max_length=20, blank=True)),
                ('client', models.ForeignKey(to='core.Client')),
            ],
        ),
    ]

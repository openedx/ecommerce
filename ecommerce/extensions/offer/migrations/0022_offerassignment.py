# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-12-05 16:03
from __future__ import unicode_literals

from __future__ import absolute_import
import django.db.models.deletion
import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0005_auto_20180124_1131'),
        ('offer', '0021_range_enterprise_customer_catalog'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfferAssignment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('code', models.CharField(max_length=128)),
                ('user_email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('EMAIL_PENDING', 'Email to user pending.'), ('ASSIGNED', 'Code successfully assigned to user.'), ('REDEEMED', 'Code has been redeemed by user.'), ('EMAIL_BOUNCED', 'Email to user bounced.'), ('REVOKED', 'Code has been revoked for this user.')], default='EMAIL_PENDING', max_length=255)),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='offer.ConditionalOffer')),
                ('voucher_application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='voucher.VoucherApplication')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
    ]

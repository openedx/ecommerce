# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import fernet_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdyenConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('cse_public_key', models.CharField(max_length=255)),
                ('merchant_account_code', models.CharField(max_length=255)),
                ('payment_api_url', models.CharField(max_length=255)),
                ('notifications_hmac_key', fernet_fields.fields.EncryptedCharField(max_length=255)),
                ('web_service_password', fernet_fields.fields.EncryptedCharField(max_length=255)),
                ('web_service_username', models.CharField(max_length=255)),
                ('site', models.OneToOneField(to='sites.Site')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]

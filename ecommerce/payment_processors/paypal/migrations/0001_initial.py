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
            name='PaypalConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('client_id', models.CharField(max_length=255)),
                ('client_secret', fernet_fields.fields.EncryptedCharField(max_length=255)),
                ('mode', models.CharField(default=b'sandbox', max_length=8, choices=[(b'live', b'live'), (b'sandbox', b'sandbox')])),
                ('retry_attempts', models.IntegerField(default=1)),
                ('site', models.OneToOneField(to='sites.Site')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PaypalWebProfile',
            fields=[
                ('id', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
        ),
    ]

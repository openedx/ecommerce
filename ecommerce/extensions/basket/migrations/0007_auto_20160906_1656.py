# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import oscar.models.fields.autoslugfield
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0006_basket_site'),
    ]

    operations = [
        migrations.CreateModel(
            name='BasketAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('value_text', models.TextField(verbose_name='Text Attribute', blank=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='BasketAttributeType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128, verbose_name='Name')),
                ('code', oscar.models.fields.autoslugfield.AutoSlugField(populate_from=b'name', editable=False, max_length=128, blank=True, unique=True, verbose_name='Code')),
            ],
        ),
        migrations.AddField(
            model_name='basketattribute',
            name='attribute_type',
            field=models.ForeignKey(verbose_name='Attribute Type', to='basket.BasketAttributeType'),
        ),
        migrations.AddField(
            model_name='basketattribute',
            name='basket',
            field=models.ForeignKey(verbose_name='Basket', to='basket.Basket'),
        ),
    ]

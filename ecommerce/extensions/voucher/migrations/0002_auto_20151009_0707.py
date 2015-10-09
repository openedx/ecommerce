# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_auto_20150803_1406'),
        ('voucher', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucher',
            name='active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='voucher',
            name='course_id',
            field=models.ForeignKey(related_name='course', to='courses.Course', null=True),
        ),
        migrations.AddField(
            model_name='voucher',
            name='created_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='voucher',
            name='discount',
            field=models.IntegerField(default=100),
        ),
        migrations.AddField(
            model_name='voucher',
            name='enrollment_code',
            field=models.CharField(max_length=255, unique=True, null=True),
        ),
        migrations.AddField(
            model_name='voucher',
            name='price',
            field=models.FloatField(null=True),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('order', '0009_auto_20150709_1205'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnrollmentCode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=255)),
                ('price', models.IntegerField()),
                ('created_at', models.DateTimeField()),
                ('created_by_id', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('order_id', models.ForeignKey(to='order.Order')),
            ],
        ),
    ]

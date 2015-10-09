# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0001_initial'),
        ('courses', '0004_auto_20150803_1406'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EnrollmentCode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField()),
                ('discount', models.IntegerField(default=100)),
                ('author_id', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('course', models.ForeignKey(related_name='course', to='courses.Course')),
                ('voucher', models.ForeignKey(to='voucher.Voucher', null=True)),
            ],
        ),
    ]

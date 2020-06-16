# -*- coding: utf-8 -*-


import jsonfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0002_range_catalog'),
    ]

    operations = [
        migrations.AddField(
            model_name='range',
            name='catalog_query',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='range',
            name='course_seat_types',
            field=jsonfield.fields.JSONField(null=True),
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_historicalcourse'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='thumbnail_url',
            field=models.URLField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='thumbnail_url',
            field=models.URLField(null=True, blank=True),
            preserve_default=True,
        ),
    ]

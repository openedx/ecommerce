# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0007_auto_20161026_0856'),
    ]

    operations = [
        migrations.AddField(
            model_name='range',
            name='course_catalog',
            field=models.PositiveIntegerField(help_text='Course catalog id from the Catalog Service.', null=True, blank=True),
        ),
    ]

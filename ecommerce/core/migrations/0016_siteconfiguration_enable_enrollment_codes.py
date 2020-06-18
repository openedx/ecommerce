# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_siteconfiguration_from_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='enable_enrollment_codes',
            field=models.BooleanField(default=False, help_text='Enable the creation of enrollment codes.', verbose_name='Enable enrollment codes'),
        ),
    ]

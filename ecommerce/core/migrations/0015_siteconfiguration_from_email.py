# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_enrollment_code_switch'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='from_email',
            field=models.CharField(help_text='Address from which emails are sent.', max_length=255, null=True, verbose_name='From email', blank=True),
        ),
    ]

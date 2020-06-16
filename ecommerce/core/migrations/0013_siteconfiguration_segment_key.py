# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_businessclient'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='segment_key',
            field=models.CharField(help_text='Segment write/API key.', max_length=255, null=True, verbose_name='Segment key', blank=True),
        ),
    ]

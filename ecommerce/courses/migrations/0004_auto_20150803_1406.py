# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_auto_20150618_1108'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='verification_deadline',
            field=models.DateTimeField(help_text='Last date/time on which verification for this product can be submitted.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='verification_deadline',
            field=models.DateTimeField(help_text='Last date/time on which verification for this product can be submitted.', null=True, blank=True),
            preserve_default=True,
        ),
    ]

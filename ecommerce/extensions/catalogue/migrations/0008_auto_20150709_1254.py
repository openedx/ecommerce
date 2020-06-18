# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0007_auto_20150709_1205'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalproduct',
            name='expires',
            field=models.DateTimeField(help_text='Last date/time on which this product can be purchased.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='product',
            name='expires',
            field=models.DateTimeField(help_text='Last date/time on which this product can be purchased.', null=True, blank=True),
            preserve_default=True,
        ),
    ]

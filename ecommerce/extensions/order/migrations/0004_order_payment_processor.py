# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0003_auto_20150224_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_processor',
            field=models.CharField(max_length=32, verbose_name='Payment Processor', blank=True),
            preserve_default=True,
        ),
    ]

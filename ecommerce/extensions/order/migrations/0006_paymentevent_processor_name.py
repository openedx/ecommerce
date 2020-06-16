# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0005_deprecate_order_payment_processor'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentevent',
            name='processor_name',
            field=models.CharField(max_length=32, null=True, verbose_name='Payment Processor', blank=True),
            preserve_default=True,
        ),
    ]

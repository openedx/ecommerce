# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0004_order_payment_processor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_processor',
            field=models.CharField(max_length=32, null=True, verbose_name='Payment Processor', blank=True),
            preserve_default=True,
        ),
    ]

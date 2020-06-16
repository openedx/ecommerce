# -*- coding: utf-8 -*-


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0009_auto_20150709_1205'),
        ('core', '0012_businessclient'),
        ('invoice', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalinvoice',
            name='business_client',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='core.BusinessClient', null=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='order',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='order.Order', null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='business_client',
            field=models.ForeignKey(to='core.BusinessClient', null=True, on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='invoice',
            name='order',
            field=models.ForeignKey(to='order.Order', null=True, on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='basket',
            field=models.ForeignKey(blank=True, to='basket.Basket', null=True, on_delete=models.CASCADE),
        ),
    ]

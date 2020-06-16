# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0010_catalog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catalog',
            name='stock_records',
            field=models.ManyToManyField(related_name='catalogs', to='partner.StockRecord', blank=True),
        ),
    ]

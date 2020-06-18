# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
        ('catalogue', '0009_credit_hours_attr'),
    ]

    operations = [
        migrations.CreateModel(
            name='Catalog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('partner', models.ForeignKey(related_name='catalogs', to='partner.Partner', on_delete=models.CASCADE)),
                ('stock_records', models.ManyToManyField(to='partner.StockRecord', blank=True)),
            ],
        ),
    ]

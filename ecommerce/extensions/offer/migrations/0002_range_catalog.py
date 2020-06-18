# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0013_coupon_product_class'),
        ('offer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='range',
            name='catalog',
            field=models.ForeignKey(related_name='ranges', blank=True, to='catalogue.Catalog', null=True, on_delete=models.CASCADE),
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0008_delete_order_payment_processor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalorder',
            name='date_placed',
            field=models.DateTimeField(db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='order',
            name='date_placed',
            field=models.DateTimeField(db_index=True),
            preserve_default=True,
        ),
    ]

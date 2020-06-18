# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0003_orderlinevouchers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderlinevouchers',
            name='vouchers',
            field=models.ManyToManyField(related_name='order_line_vouchers', to='voucher.Voucher'),
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0009_auto_20150709_1205'),
        ('voucher', '0002_couponvouchers'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderLineVouchers',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('line', models.ForeignKey(related_name='order_line_vouchers', to='order.Line', on_delete=models.CASCADE)),
                ('vouchers', models.ManyToManyField(related_name='order_line_vouchers', to='voucher.Voucher', blank=True)),
            ],
        ),
    ]

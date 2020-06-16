# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0013_coupon_product_class'),
        ('voucher', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CouponVouchers',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('coupon', models.ForeignKey(related_name='coupon_vouchers', to='catalogue.Product', on_delete=models.CASCADE)),
                ('vouchers', models.ManyToManyField(related_name='coupon_vouchers', to='voucher.Voucher', blank=True)),
            ],
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('refund', '0001_squashed_0002_auto_20150515_2220'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalrefund',
            name='status',
            field=models.CharField(max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Payment Refund Error', b'Payment Refund Error'), (b'Payment Refunded', b'Payment Refunded'), (b'Revocation Error', b'Revocation Error'), (b'Complete', b'Complete')]),
        ),
        migrations.AlterField(
            model_name='historicalrefundline',
            name='status',
            field=models.CharField(max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Revocation Error', b'Revocation Error'), (b'Denied', b'Denied'), (b'Complete', b'Complete')]),
        ),
        migrations.AlterField(
            model_name='refund',
            name='status',
            field=models.CharField(max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Payment Refund Error', b'Payment Refund Error'), (b'Payment Refunded', b'Payment Refunded'), (b'Revocation Error', b'Revocation Error'), (b'Complete', b'Complete')]),
        ),
        migrations.AlterField(
            model_name='refundline',
            name='status',
            field=models.CharField(max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Revocation Error', b'Revocation Error'), (b'Denied', b'Denied'), (b'Complete', b'Complete')]),
        ),
    ]

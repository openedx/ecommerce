# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0011_paypalprocessorconfiguration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paypalprocessorconfiguration',
            name='retry_attempts',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Number of times to retry failing Paypal client actions (e.g., payment creation, payment execution)'),
        ),
    ]

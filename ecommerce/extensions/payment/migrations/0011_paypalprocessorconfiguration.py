# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0010_create_client_side_checkout_flag'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaypalProcessorConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('retry_attempts', models.PositiveSmallIntegerField(default=0, verbose_name='Number of times to retry failing Paypal client actions')),
            ],
            options={
                'verbose_name': 'Paypal Processor Configuration',
            },
        ),
    ]

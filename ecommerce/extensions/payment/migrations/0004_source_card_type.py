# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0003_create_payment_processor_response'),
    ]

    operations = [
        migrations.AddField(
            model_name='source',
            name='card_type',
            field=models.CharField(blank=True, max_length=255, null=True, choices=[(b'visa', b'Visa'), (b'discover', b'Discover'), (b'mastercard', b'MasterCard'), (b'american_express', b'American Express')]),
            preserve_default=True,
        ),
    ]

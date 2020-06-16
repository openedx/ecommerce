# -*- coding: utf-8 -*-


from django.db import migrations, models

import ecommerce.extensions.offer.models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0005_conditionaloffer_email_domains'),
    ]

    operations = [
        migrations.AlterField(
            model_name='range',
            name='course_seat_types',
            field=models.CharField(blank=True, max_length=255, null=True, validators=[ecommerce.extensions.offer.models.validate_credit_seat_type]),
        ),
    ]

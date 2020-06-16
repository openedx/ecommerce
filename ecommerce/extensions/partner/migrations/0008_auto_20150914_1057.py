# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0007_auto_20150914_0841'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='short_code',
            field=models.CharField(unique=True, max_length=8),
        ),
    ]

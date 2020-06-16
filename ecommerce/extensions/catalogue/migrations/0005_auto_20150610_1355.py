# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0004_auto_20150609_0129'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalproduct',
            name='changed_by',
        ),
        migrations.RemoveField(
            model_name='historicalproductattributevalue',
            name='changed_by',
        ),
        migrations.RemoveField(
            model_name='product',
            name='changed_by',
        ),
        migrations.RemoveField(
            model_name='productattributevalue',
            name='changed_by',
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0017_enrollment_code_product_class'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['-date_created'], 'get_latest_by': 'date_created', 'verbose_name': 'Product', 'verbose_name_plural': 'Products'},
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0019_enrollment_code_idverifyreq_attribute'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['-date_created'], 'verbose_name': 'Product', 'verbose_name_plural': 'Products'},
        ),
    ]

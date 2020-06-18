# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0008_range_course_catalog'),
    ]

    operations = [
        migrations.AddField(
            model_name='range',
            name='enterprise_customer',
            field=models.UUIDField(help_text='UUID for an EnterpriseCustomer from the Enterprise Service.', null=True, blank=True),
        ),
    ]

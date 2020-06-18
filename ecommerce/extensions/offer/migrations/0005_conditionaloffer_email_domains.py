# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0004_auto_20160530_0944'),
    ]

    operations = [
        migrations.AddField(
            model_name='conditionaloffer',
            name='email_domains',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]

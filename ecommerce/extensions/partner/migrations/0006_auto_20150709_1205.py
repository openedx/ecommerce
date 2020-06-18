# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0005_auto_20150610_1355'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='users',
            field=models.ManyToManyField(related_name='partners', verbose_name='Users', to=settings.AUTH_USER_MODEL, blank=True),
            preserve_default=True,
        ),
    ]

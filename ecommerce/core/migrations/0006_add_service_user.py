# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import migrations, models

User = get_user_model()


class Migration(migrations.Migration):

    def add_service_user(apps, schema_editor):
        service_user = User.objects.create(
            username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME,
            is_superuser=True
        )
        service_user.set_unusable_password()
        service_user.save()

    def remove_service_user(apps, schema_editor):
        User.objects.get(username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME).delete()

    dependencies = [
        ('core', '0005_auto_20150924_0123'),
    ]

    operations = [
        migrations.RunPython(add_service_user, remove_service_user)
    ]

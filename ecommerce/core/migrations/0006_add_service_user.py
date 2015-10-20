# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

service_worker_username = settings.ECOMMERCE_SERVICE_WORKER_USERNAME


def add_service_user(apps, schema_editor):
    User = apps.get_model('core', 'User')

    service_user = User.objects.create(
        username=service_worker_username,
        is_superuser=True
    )
    service_user.set_unusable_password()
    service_user.save()


def remove_service_user(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.get(username=settings.service_worker_username).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_auto_20150924_0123'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(add_service_user, remove_service_user)
    ]

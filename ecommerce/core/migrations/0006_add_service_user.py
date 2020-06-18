# -*- coding: utf-8 -*-


from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations


class Migration(migrations.Migration):

    def add_service_user(apps, schema_editor):
        app_name, _, model_name = settings.AUTH_USER_MODEL.rpartition('.')
        User = apps.get_model(app_name, model_name)

        service_user = User.objects.create(
            username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME,
            is_superuser=True
        )
        service_user.password = make_password(None)
        service_user.save()

    def remove_service_user(apps, schema_editor):
        app_name, _, model_name = settings.AUTH_USER_MODEL.rpartition('.')
        User = apps.get_model(app_name, model_name)

        User.objects.get(username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME).delete()

    dependencies = [
        ('core', '0005_auto_20150924_0123'),
    ]

    operations = [
        migrations.RunPython(add_service_user, remove_service_user)
    ]

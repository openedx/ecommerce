# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Permission
from django.db import migrations

User = get_user_model()


class Migration(migrations.Migration):

    def alter_service_user_privileges(apps, schema_editor):
        # Explicitly create permissions. Permissions are not created until after
        # Django has finished running migrations, meaning that when migrations are
        # run against a fresh database (e.g., while running tests), any which depend
        # on the existence of a permission will fail.
        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=0, apps=apps)
            app_config.models_module = None

        service_user = User.objects.get(username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME)

        # The ecommerce worker service user should have permissions to fulfill orders,
        # but should not be a superuser.
        change_order_permission = Permission.objects.get(codename='change_order')
        service_user.user_permissions.add(change_order_permission)
        service_user.is_staff = True
        service_user.is_superuser = False

        service_user.save()

    def restore_service_user_privileges(apps, schema_editor):
        service_user = User.objects.get(username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME)

        change_order_permission = Permission.objects.get(codename='change_order')
        service_user.user_permissions.remove(change_order_permission)
        service_user.is_staff = False
        service_user.is_superuser = True

        service_user.save()

    dependencies = [
        ('core', '0008_client'),
    ]

    operations = [
        migrations.RunPython(alter_service_user_privileges, restore_service_user_privileges)
    ]

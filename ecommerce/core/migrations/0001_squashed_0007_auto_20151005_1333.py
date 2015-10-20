# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.contrib.auth import get_user_model

from django.db import migrations, models
import jsonfield.fields
import django.contrib.auth.models
from django.conf import settings
import django.utils.timezone
import django.core.validators


# Functions from the following migrations need manual copying.
# Move them and any dependencies into this file, then update the
# RunPython operations to refer to the local versions:
# ecommerce.core.migrations.0005_auto_20150924_0123
# ecommerce.core.migrations.0007_auto_20151005_1333
# ecommerce.core.migrations.0006_add_service_user


service_worker_username = settings.ECOMMERCE_SERVICE_WORKER_USERNAME
User = get_user_model()


def add_service_user(apps, schema_editor):
    User.objects.create_superuser(
        username=service_worker_username,
        email=None,
        password=None
    )


def remove_service_user(apps, schema_editor):
    User.objects.get(username=settings.service_worker_username).delete()


class Migration(migrations.Migration):

    replaces = [(b'core', '0001_initial'), (b'core', '0002_auto_20150826_1455'), (b'core', '0003_auto_20150914_1120'), (b'core', '0004_auto_20150915_1023'), (b'core', '0005_auto_20150924_0123'), (b'core', '0006_add_service_user'), (b'core', '0007_auto_20151005_1333')]

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(null=True, verbose_name='last login', blank=True)),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, max_length=30, validators=[django.core.validators.RegexValidator('^[\\w.@+-]+$', 'Enter a valid username. This value may contain only letters, numbers and @/./+/-/_ characters.', 'invalid')], help_text='Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.', unique=True, verbose_name='username')),
                ('first_name', models.CharField(max_length=30, verbose_name='first name', blank=True)),
                ('last_name', models.CharField(max_length=30, verbose_name='last name', blank=True)),
                ('email', models.EmailField(max_length=254, verbose_name='email address', blank=True)),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('full_name', models.CharField(max_length=255, null=True, verbose_name='Full Name', blank=True)),
                ('tracking_context', jsonfield.fields.JSONField(null=True, blank=True)),
                ('groups', models.ManyToManyField(related_query_name='user', related_name='user_set', to=b'auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(related_query_name='user', related_name='user_set', to=b'auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions')),
            ],
            options={
                'db_table': 'ecommerce_user',
                'get_latest_by': 'date_joined',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.RunPython(
            code=add_service_user,
            reverse_code=remove_service_user,
        ),
    ]

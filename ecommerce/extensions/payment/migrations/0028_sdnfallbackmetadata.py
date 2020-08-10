# Generated by Django 2.2.15 on 2020-08-11 13:56

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0027_auto_20200811_1356'),
    ]

    operations = [
        migrations.CreateModel(
            name='SDNFallbackMetadata',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_checksum', models.CharField(max_length=255, validators=[django.core.validators.MinLengthValidator(1)])),
                ('download_timestamp', models.DateTimeField(auto_now_add=True)),
                ('import_timestamp', models.DateTimeField(blank=True, null=True)),
                ('import_state', models.CharField(choices=[('New', 'New'), ('Current', 'Current'), ('Discard', 'Discard')], default='New', max_length=255, unique=True, validators=[django.core.validators.MinLengthValidator(1)])),
            ],
        ),
    ]

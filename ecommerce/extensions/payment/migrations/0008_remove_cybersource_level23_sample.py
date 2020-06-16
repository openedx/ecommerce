# -*- coding: utf-8 -*-


from django.db import migrations

SAMPLE_NAME = 'send_level_2_3_details_to_cybersource'


def create_sample(apps, schema_editor):
    Sample = apps.get_model('waffle', 'Sample')

    Sample.objects.create(
        name=SAMPLE_NAME,
        percent=0,
        note='When this sample is active, Level 2/3 transaction data will be sent to CyberSource.')


def delete_sample(apps, schema_editor):
    Sample = apps.get_model('waffle', 'Sample')

    try:
        Sample.objects.get(name=SAMPLE_NAME).delete()
    except Sample.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('payment', '0007_add_cybersource_level23_sample'),
    ]

    operations = [
        migrations.RunPython(delete_sample, create_sample)
    ]

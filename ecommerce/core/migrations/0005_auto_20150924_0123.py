# -*- coding: utf-8 -*-


from django.db import migrations


def create_switch(apps, schema_editor):
    """Create and activate the publish_course_modes_to_lms switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='publish_course_modes_to_lms', defaults={'active': True})


def delete_switch(apps, schema_editor):
    """Delete the publish_course_modes_to_lms switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='publish_course_modes_to_lms').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_auto_20150915_1023'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]

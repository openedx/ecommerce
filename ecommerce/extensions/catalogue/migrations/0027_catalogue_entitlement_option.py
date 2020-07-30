# -*- coding: utf-8 -*-


from django.db import migrations, models
from oscar.core.loading import get_model

Option = get_model('catalogue', 'Option')


def create_entitlement_option(apps, schema_editor):
    """ Create catalogue entitlement option. """
    Option.skip_history_when_saving = True
    course_entitlement_option = Option()
    course_entitlement_option.name = 'Course Entitlement'
    course_entitlement_option.code = 'course_entitlement'
    course_entitlement_option.type = Option.OPTIONAL
    course_entitlement_option.save()


def remove_entitlement_option(apps, schema_editor):
    """ Remove course entitlement option """
    Option.skip_history_when_saving = True
    course_entitlement_option = Option.objects.get(code='course_entitlement')
    course_entitlement_option.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0026_course_entitlement_attr_change')
    ]

    operations = [
        migrations.RunPython(create_entitlement_option, remove_entitlement_option),
    ]

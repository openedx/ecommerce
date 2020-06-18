# -*- coding: utf-8 -*-


from django.db import migrations


def create_flag(apps, schema_editor):
    """
    Create the disable_microfrontend_for_basket_page flag if it does not already exist.

    Set `everyone` to None so that it's Unknown in the admin
    """
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.get_or_create(
        name='disable_microfrontend_for_basket_page',
        defaults={'everyone': None, 'superusers': False}
    )


def delete_flag(apps, schema_editor):
    """Delete the disable_microfrontend_for_basket_page flag."""
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.filter(name='disable_microfrontend_for_basket_page').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0019_auto_20180628_2011'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_flag, reverse_code=delete_flag),
    ]

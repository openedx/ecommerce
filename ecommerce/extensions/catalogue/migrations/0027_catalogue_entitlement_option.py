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
        migrations.AddField(
            model_name='option',
            name='help_text',
            field=models.CharField(blank=True, help_text='Help text shown to the user on the add to basket form', max_length=255, null=True, verbose_name='Help text'),
        ),
        migrations.AddField(
            model_name='option',
            name='option_group',
            field=models.ForeignKey(blank=True, help_text='Select an option group if using type "Option" or "Multi Option"', null=True, on_delete=models.deletion.CASCADE, related_name='product_options', to='catalogue.attributeoptiongroup', verbose_name='Option Group'),
        ),
        migrations.AddField(
            model_name='option',
            name='order',
            field=models.IntegerField(blank=True, db_index=True, help_text='Controls the ordering of product options on product detail pages', null=True, verbose_name='Ordering'),
        ),
        migrations.AddField(
            model_name='option',
            name='required',
            field=models.BooleanField(default=False, verbose_name='Is this option required?'),
        ),
        migrations.AlterField(
            model_name='option',
            name='name',
            field=models.CharField(db_index=True, max_length=128, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='option',
            name='type',
            field=models.CharField(choices=[('text', 'Text'), ('integer', 'Integer'), ('boolean', 'True / False'), ('float', 'Float'), ('date', 'Date'), ('select', 'Select'), ('radio', 'Radio'), ('multi_select', 'Multi select'), ('checkbox', 'Checkbox')], default='text', max_length=255, verbose_name='Type'),
        ),
        migrations.RunPython(create_entitlement_option, remove_entitlement_option),
    ]

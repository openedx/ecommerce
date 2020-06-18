# -*- coding: utf-8 -*-


from django.db import migrations, models


def add_short_code_data(apps, schema_editor):
    """Get the value of the 'code' field from the Partner table and add it to
    the field 'short_code'.
    """
    Partner = apps.get_model('partner', 'Partner')
    Partner.skip_history_when_saving = True

    partners = Partner.objects.all()
    for partner in partners:
        partner.short_code = partner.code
        partner.save()


def reverse_short_code_data(apps, schema_editor):
    """Backward data migration for field 'short_code'."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0006_auto_20150709_1205'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='partner',
            options={'verbose_name': 'Partner', 'verbose_name_plural': 'Partners'},
        ),
        migrations.AddField(
            model_name='partner',
            name='short_code',
            field=models.CharField(max_length=8, unique=True, null=True),
        ),
        migrations.RunPython(add_short_code_data, reverse_short_code_data),
    ]

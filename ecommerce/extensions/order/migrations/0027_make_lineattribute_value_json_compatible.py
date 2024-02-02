# -*- coding: utf-8 -*-
from django.core.paginator import Paginator
from django.db import migrations


def make_lineattribute_value_json_compatible(apps, schema_editor):
    """
    Makes line attribute value json compatible.
    """
    LineAttribute = apps.get_model("order", "LineAttribute")
    attributes = LineAttribute.objects.order_by('id')
    paginator = Paginator(attributes, 1000)

    for page_number in paginator.page_range:
        page = paginator.page(page_number)
        updates = []

        for obj in page.object_list:
            obj.value = '"{}"'.format(obj.value)
            updates.append(obj)

        LineAttribute.objects.bulk_update(updates, ['value'])


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0026_auto_20231108_1355'),
    ]

    operations = [
        migrations.RunPython(make_lineattribute_value_json_compatible, migrations.RunPython.noop),
    ]

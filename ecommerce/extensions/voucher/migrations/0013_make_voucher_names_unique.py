# Generated by Django 3.2.20 on 2023-11-14 11:20

from django.core.paginator import Paginator
from django.db import migrations


def make_voucher_names_unique(apps, schema_editor):
    """
    Appends a number to voucher names.
    """
    Voucher = apps.get_model('voucher', 'Voucher')
    vouchers = Voucher.objects.order_by('date_created')
    paginator = Paginator(vouchers, 1000)

    for page_number in paginator.page_range:
        page = paginator.page(page_number)
        updates = []

        for obj in page.object_list:
            obj.name = '%d - %s' % (obj.id, obj.name)
            if len(obj.name) > 128:
                obj.name = obj.name[:128]
            updates.append(obj)

        Voucher.objects.bulk_update(updates, ['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0012_voucher_is_public'),
    ]

    operations = [
        migrations.RunPython(make_voucher_names_unique, migrations.RunPython.noop),
    ]

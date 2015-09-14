# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


def add_partner_and_update_order_number(apps, schema_editor):
    """ Updating existing orders. Adding relation between order and partner.
    """

    Order = apps.get_model('order', 'Order')
    Partner = apps.get_model('partner', 'Partner')

    partner = Partner.objects.get(id=1)

    orders = Order.objects.all()

    # Update all existing basket with edx partner
    orders.update(partner=partner)


def remove_partner_and_update_order_number(apps, schema_editor):
    # This method is for backward compatibility
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0006_auto_20150709_1205'),
        ('order', '0009_auto_20150709_1205'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalorder',
            name='partner',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='partner.Partner', null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='partner',
            field=models.ForeignKey(related_name='orders', to='partner.Partner', null=True, blank=True),
            preserve_default=False,
        ),
        migrations.RunPython(add_partner_and_update_order_number, remove_partner_and_update_order_number),
        migrations.AlterField(
            model_name='order',
            name='partner',
            field=models.ForeignKey(related_name='orders', blank=False, to='partner.Partner', null=False),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def create_catalog(apps, schema_editor):
    """

    Create all Product Catalog data for a sandbox, such as our Partner and Product Stock.

    """
    # Create all our Product Types.
    Partner = apps.get_model("partner", "Partner")
    edx = Partner(code="edx", name="edX")
    edx.save()

    StockRecord = apps.get_model("partner", "StockRecord")
    Product = apps.get_model("catalogue", "Product")
    honor_seat = Product.objects.get(upc="000000000002")
    honor_stock = StockRecord(
        product=honor_seat,
        partner_sku="SEAT-HONOR-EDX-DEMOX-DEMO-COURSE",
        price_retail="0",
        partner=edx,
        price_excl_tax="0",
        cost_price="0"
    )
    honor_stock.save()


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0002_auto_20141007_2032'),
    ]

    operations = [
        migrations.RunPython(create_catalog),
    ]

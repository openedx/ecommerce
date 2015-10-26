# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0006_basket_partner'),
    ]

    operations = [
        migrations.AlterField(
            model_name='basket',
            name='partner',
            field=models.ForeignKey(related_name='baskets', default=1, to='partner.Partner'),
        ),
    ]

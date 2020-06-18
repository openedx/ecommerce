# -*- coding: utf-8 -*-


import oscar
from django.db import migrations, models

# Depricated. We switched to the Coupon product class.


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0011_auto_20151019_0639')
    ]
    operations = []

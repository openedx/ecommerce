# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-21 05:01
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('waffle', '0001_initial'),
        ('basket', '0009_auto_20170215_2229'),
    ]

    operations = [
        # NOTE (CCB): This migration is no longer needed. Eventually, it should be squashed out.
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]

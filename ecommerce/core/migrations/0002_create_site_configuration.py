# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        ('partner', '0002_create_site_configuration'),
        ('core', '0001_squashed_0007_auto_20151005_1333'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('lms_url_root', models.URLField(help_text="Root URL of this site's LMS (e.g. https://courses.stage.edx.org)", verbose_name='LMS base url for custom site/microsite')),
                ('theme_scss_path', models.CharField(help_text='Path to scss files of the custom site theme', max_length=255, verbose_name='Path to custom site theme')),
                ('payment_processors', models.CharField(help_text="Comma-separated list of processor names: 'cybersource,paypal'", max_length=255, verbose_name='Payment processors')),
                ('partner', models.ForeignKey(to='partner.Partner')),
                ('site', models.OneToOneField(to='sites.Site')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='siteconfiguration',
            unique_together=set([('site', 'partner')]),
        ),
    ]

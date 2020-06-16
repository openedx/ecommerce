# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0007_auto_20150914_0841'),
        ('sites', '0001_initial'),
        ('core', '0002_auto_20150826_1455'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('lms_url_root', models.URLField(help_text="Root URL of this site's LMS (e.g. https://courses.stage.edx.org)", verbose_name='LMS base url for custom site/microsite')),
                ('theme_scss_path', models.CharField(help_text='Path to scss files of the custom site theme', max_length=255, verbose_name='Path to custom site theme')),
                ('payment_processors', models.CharField(help_text="Comma-separated list of processor names: 'cybersource,paypal'", max_length=255, verbose_name='Payment processors')),
                ('partner', models.ForeignKey(to='partner.Partner', on_delete=models.CASCADE)),
                ('site', models.ForeignKey(to='sites.Site', on_delete=models.CASCADE)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='siteconfiguration',
            unique_together=set([('site', 'partner')]),
        ),
    ]

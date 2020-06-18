# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        ('referrals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='referral',
            name='site',
            field=models.ForeignKey(to='sites.Site', null=True, on_delete=models.CASCADE),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='referral',
            name='utm_campaign',
            field=models.CharField(default='', max_length=255, verbose_name='UTM Campaign', blank=True),
        ),
        migrations.AddField(
            model_name='referral',
            name='utm_content',
            field=models.CharField(default='', max_length=255, verbose_name='UTM Content', blank=True),
        ),
        migrations.AddField(
            model_name='referral',
            name='utm_created_at',
            field=models.DateTimeField(default=None, null=True, verbose_name='UTM Created At', blank=True),
        ),
        migrations.AddField(
            model_name='referral',
            name='utm_medium',
            field=models.CharField(default='', max_length=255, verbose_name='UTM Medium', blank=True),
        ),
        migrations.AddField(
            model_name='referral',
            name='utm_source',
            field=models.CharField(default='', max_length=255, verbose_name='UTM Source', blank=True),
        ),
        migrations.AddField(
            model_name='referral',
            name='utm_term',
            field=models.CharField(default='', max_length=255, verbose_name='UTM Term', blank=True),
        ),
        migrations.AlterField(
            model_name='referral',
            name='affiliate_id',
            field=models.CharField(default='', max_length=255, verbose_name='Affiliate ID', blank=True),
        ),
    ]

# -*- coding: utf-8 -*-
"""
This migration exists to fix the error introduced by https://github.com/edx/ecommerce/pull/968. The 0002 migration
has been updated to setup the site column correctly for new installations. This migration ensures installations
that previously ran 0002 have the column setup correctly.
"""



from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('referrals', '0002_auto_20161011_1728'),
    ]

    operations = [

        migrations.AlterField(
            model_name='referral',
            name='site',
            field=models.ForeignKey(to='sites.Site', null=True, on_delete=models.CASCADE),
        ),
    ]

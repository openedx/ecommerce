# -*- coding: utf-8 -*-


from django.db import migrations, models


# NOTE (CCB): This migration used to create a partner and product. Our Partner and Product models
# have expanded, and this migration is no longer needed. It should be removed when we eventually
# squash migrations: https://docs.djangoproject.com/en/1.8/topics/migrations/#squashing-migrations.
class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0002_auto_20141007_2032'),
    ]

    operations = []

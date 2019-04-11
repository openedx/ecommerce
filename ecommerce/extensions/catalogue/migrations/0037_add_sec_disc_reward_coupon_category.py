# -*- coding: utf-8 -*-

""" 
Adds a new couple category that will be used to track rewards given
to members of the community who make security disclosures.
"""

from __future__ import unicode_literals

from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model('catalogue', 'Category')

COUPON_CATEGORY_NAME = 'Coupons'

SECURITY_DISCLOSURE_REWARD_CATEGORY = 'Security Disclosure Reward'

def create_security_disclosure_reward_category(apps, schema_editor):
    """ Create coupon category for rewarding security disclosures. """
    create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME,
                                             SECURITY_DISCLOSURE_REWARD_CATEGORY))

def remove_security_disclosure_reward_category(apps, schema_editor):
    """ Remove the security disclosure reward category. """
    Category.objects.get(
        name=COUPON_CATEGORY_NAME
    ).get_children().filter(
        name=SECURITY_DISCLOSURE_REWARD_CATEGORY
    ).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0036_coupon_notify_email_attribute'),
    ]

    operations = [
        migrations.RunPython(create_security_disclosure_reward_category,
                             remove_security_disclosure_reward_category)
    ]

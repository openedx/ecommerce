from __future__ import absolute_import

import os

from ecommerce.settings.base import *


########## URL CONFIGURATION
# Used to construct LMS URLs; must include a trailing slash
LMS_URL_ROOT = 'http://127.0.0.1:8000/'

# The location of the LMS student dashboard
LMS_DASHBOARD_URL = LMS_URL_ROOT + 'dashboard'
########## END URL CONFIGURATION


########## TEST SETTINGS
INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

class DisableMigrations(object):
    """Override method calls on the MIGRATION_MODULES dictionary.

    If the `makemigrations` command has not been run for an app, the
    `migrate` command treats that app as unmigrated, creating tables
    directly from the models just like the now-defunct `syncdb` command
    used to do. These overrides are used to force Django to treat apps
    in this project as unmigrated.

    Django 1.8 features the `--keepdb` flag for exactly this purpose,
    but we don't have that luxury in 1.7.

    For more context, see http://goo.gl/Fr4qyE.
    """
    def __contains__(self, item):
        """Make it appear as if all apps are contained in the dictionary."""
        return True

    def __getitem__(self, item):
        """Force Django to look for migrations in a nonexistent package."""
        return 'notmigrations'

if str(os.environ.get('DISABLE_MIGRATIONS')) == 'True':
    MIGRATION_MODULES = DisableMigrations()
########## END TEST SETTINGS

########## IN-MEMORY TEST DATABASE
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    },
}
########## END IN-MEMORY TEST DATABASE

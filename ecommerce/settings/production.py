"""Production settings and globals."""


import codecs
from os import environ
from urllib.parse import urljoin

import yaml
from corsheaders.defaults import default_headers as corsheaders_default_headers
# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

from ecommerce.settings.base import *

# Protocol used for construcing absolute callback URLs
PROTOCOL = 'https'

# Enable offline compression of CSS/JS
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

# Email configuration
EMAIL_BACKEND = 'django_ses.SESBackend'

# Minify CSS
COMPRESS_CSS_FILTERS += [
    'compressor.filters.cssmin.CSSMinFilter',
]

LOGGING['handlers']['local']['level'] = 'INFO'


def get_env_setting(setting):
    """ Get the environment setting or return exception """
    try:
        return environ[setting]
    except KeyError:
        error_msg = "Set the %s env variable" % setting
        raise ImproperlyConfigured(error_msg)


# HOST CONFIGURATION
# See: https://docs.djangoproject.com/en/1.5/releases/1.5/#allowed-hosts-required-in-production
ALLOWED_HOSTS = ['*']
# END HOST CONFIGURATION

# Keep track of the names of settings that represent dicts. Instead of overriding the values in base.py,
# the values read from disk should UPDATE the pre-configured dicts.
DICT_UPDATE_KEYS = ('JWT_AUTH',)

# Set empty defaults for the logging override settings
LOGGING_ROOT_OVERRIDES = {}
LOGGING_SUBSECTION_OVERRIDES = {}

CONFIG_FILE = get_env_setting('ECOMMERCE_CFG')
with codecs.open(CONFIG_FILE, encoding='utf-8') as f:
    config_from_yaml = yaml.load(f)

    # Remove the items that should be used to update dicts, and apply them separately rather
    # than pumping them into the local vars.
    dict_updates = {key: config_from_yaml.pop(key, None) for key in DICT_UPDATE_KEYS}

    for key, value in dict_updates.items():
        if value:
            vars()[key].update(value)

    vars().update(config_from_yaml)

DB_OVERRIDES = dict(
    PASSWORD=environ.get('DB_MIGRATION_PASS', DATABASES['default']['PASSWORD']),
    ENGINE=environ.get('DB_MIGRATION_ENGINE', DATABASES['default']['ENGINE']),
    USER=environ.get('DB_MIGRATION_USER', DATABASES['default']['USER']),
    NAME=environ.get('DB_MIGRATION_NAME', DATABASES['default']['NAME']),
    HOST=environ.get('DB_MIGRATION_HOST', DATABASES['default']['HOST']),
    PORT=environ.get('DB_MIGRATION_PORT', DATABASES['default']['PORT']),
)

for override, value in DB_OVERRIDES.items():
    DATABASES['default'][override] = value

for key, value in LOGGING_ROOT_OVERRIDES.items():
    if value is None:
        del LOGGING[key]
    else:
        LOGGING[key] = value

for section, overrides in LOGGING_SUBSECTION_OVERRIDES.items():
    if overrides is None:
        del LOGGING[section]
    else:
        for key, value in overrides.items():
            if value is None:
                del LOGGING[section][key]
            else:
                LOGGING[section][key] = value


OSCAR_DEFAULT_CURRENCY = environ.get('OSCAR_DEFAULT_CURRENCY', OSCAR_DEFAULT_CURRENCY)

# PAYMENT PROCESSOR OVERRIDES
for __, configs in PAYMENT_PROCESSOR_CONFIG.items():
    for __, config in configs.items():
        config.update({
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
        })
# END PAYMENT PROCESSOR OVERRIDES

ENTERPRISE_API_URL = urljoin(ENTERPRISE_SERVICE_URL, 'api/v1/')

ENTERPRISE_CATALOG_API_URL = urljoin(ENTERPRISE_CATALOG_SERVICE_URL, 'api/v1/')

CORS_ALLOW_HEADERS = corsheaders_default_headers + (
    'use-jwt-cookie',
)

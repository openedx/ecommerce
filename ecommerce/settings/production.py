"""Production settings and globals."""
from os import environ

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

import yaml

from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config


# See: https://docs.djangoproject.com/en/dev/ref/settings/#site-id
# This needs to be set to None in order to support multitenancy
SITE_ID = None

# Enable offline compression of CSS/JS
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

# Email configuration
EMAIL_BACKEND = 'django_ses.SESBackend'

# Minify CSS
COMPRESS_CSS_FILTERS += [
    'compressor.filters.cssmin.CSSMinFilter',
]

LOGGING = get_logger_config()


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

CONFIG_FILE = get_env_setting('ECOMMERCE_CFG')

with open(CONFIG_FILE) as f:
    config_from_yaml = yaml.load(f)

vars().update(config_from_yaml)

DB_OVERRIDES = dict(
    PASSWORD=environ.get('DB_MIGRATION_PASS', DATABASES['default']['PASSWORD']),
    ENGINE=environ.get('DB_MIGRATION_ENGINE', DATABASES['default']['ENGINE']),
    USER=environ.get('DB_MIGRATION_USER', DATABASES['default']['USER']),
    NAME=environ.get('DB_MIGRATION_NAME', DATABASES['default']['NAME']),
    HOST=environ.get('DB_MIGRATION_HOST', DATABASES['default']['HOST']),
    PORT=environ.get('DB_MIGRATION_PORT', DATABASES['default']['PORT']),
)

for override, value in DB_OVERRIDES.iteritems():
    DATABASES['default'][override] = value


# PAYMENT PROCESSOR OVERRIDES
for __, config in PAYMENT_PROCESSOR_CONFIG.iteritems():
    config.update({
        'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
        'cancel_path': PAYMENT_PROCESSOR_CANCEL_PATH,
        'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
    })
# END PAYMENT PROCESSOR OVERRIDES

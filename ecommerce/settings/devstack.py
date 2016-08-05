"""Devstack settings"""
from os import environ

import yaml

from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config

LOGGING = get_logger_config(debug=True, dev_env=True, local_loglevel='DEBUG')

# Pull in base setting overrides from configuration file.
CONFIG_FILE = environ.get('ECOMMERCE_CFG')
if CONFIG_FILE is not None:
    with open(CONFIG_FILE) as f:
        overrides = yaml.load(f)
        vars().update(overrides)

DEBUG = True
ENABLE_AUTO_AUTH = True

# Load private settings
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error

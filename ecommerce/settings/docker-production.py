"""
Specific overrides to the base prod settings for a docker production deployment.

CAUTION: THIS SETTINGS FILE IS IN A WORK IN PROGRESS.
"""

import platform
from sys import stdout as sys_stdout

from .production import *  # pylint: disable=wildcard-import, unused-wildcard-import

# Requires installation of edx-arch-experiments!
# You will need to pip install this package in your docker image/container
# before using this settings file. It has intentionally been left out of
# ecommerce's normal requirements files to isolate experimental work
# from normal production environments.
INSTALLED_APPS.append(
    'edx_arch_experiments.kafka_consumer.apps.KafkaConsumerApp'
)


def get_docker_logger_config(log_dir='/var/tmp',
                             logging_env="no_env",
                             edx_filename="edx.log",
                             dev_env=False,
                             debug=False,
                             service_variant='ecommerce'):
    """
    Return the appropriate logging config dictionary. You should assign the
    result of this to the LOGGING var in your settings.
    """

    hostname = platform.node().split(".")[0]
    syslog_format = (
        "[service_variant={service_variant}]"
        "[%(name)s][env:{logging_env}] %(levelname)s "
        "[{hostname}  %(process)d] [%(filename)s:%(lineno)d] "
        "- %(message)s"
    ).format(
        service_variant=service_variant,
        logging_env=logging_env, hostname=hostname
    )

    handlers = ['console']

    logger_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s %(levelname)s %(process)d '
                          '[%(name)s] %(filename)s:%(lineno)d - %(message)s',
            },
            'syslog_format': {'format': syslog_format},
            'raw': {'format': '%(message)s'},
        },
        'handlers': {
            'console': {
                'level': 'DEBUG' if debug else 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': sys_stdout,
            },
        },
        'loggers': {
            'django': {
                'handlers': handlers,
                'propagate': True,
                'level': 'INFO'
            },
            'requests': {
                'handlers': handlers,
                'propagate': True,
                'level': 'WARNING'
            },
            'factory': {
                'handlers': handlers,
                'propagate': True,
                'level': 'WARNING'
            },
            'django.request': {
                'handlers': handlers,
                'propagate': True,
                'level': 'WARNING'
            },
            '': {
                'handlers': handlers,
                'level': 'DEBUG',
                'propagate': False
            },
        }
    }

    return logger_config

LOGGING = get_docker_logger_config()

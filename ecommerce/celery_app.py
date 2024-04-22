

import os
from celery import Celery



# TEMP: This code will be removed by ARCH-BOM on 4/22/24
# ddtrace allows celery task logs to be traced by the dd agent.
# TODO: remove this code.
try:
    from ddtrace import patch
except ImportError:
    pass
try:
    patch(celery=True)
except NameError:
    pass

# Set the default configuration module, if one is not aleady defined.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings.local')

app = Celery('ecommerce')
app.config_from_object('django.conf:settings')

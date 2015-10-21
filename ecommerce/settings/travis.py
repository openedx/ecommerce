# noinspection PyUnresolvedReferences
from ecommerce.settings.base import *
# noinspection PyUnresolvedReferences
from ecommerce.settings.test import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ecommerce_test',
        'USER': 'travis',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '',
    },
}

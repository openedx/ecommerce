import logging

from django.apps import AppConfig
from django.db import OperationalError

log = logging.getLogger(__name__)


class CoreAppConfig(AppConfig):
    name = 'ecommerce.core'
    verbose_name = 'Core'

    OPERATIONAL_ERROR_MESSAGE = 'DB error when validating configuration - most likely DB was not created yet - skipping'

    def ready(self):
        super(CoreAppConfig, self).ready()

        # Ensures that the initialized Celery app is loaded when Django starts.
        # Allows Celery tasks to bind themselves to an initialized instance of the Celery library.
        from ecommerce import celery_app  # pylint: disable=unused-variable

        from ecommerce.core.models import validate_configuration
        # Operational error means database did not contain SiteConfiguration table - ok to skip since it means there
        # are no SiteConfiguration models to validate. Also, this exception was only observed in tests and test run
        # just fine with this suppression - most likely test code hit this line before the DB is populated
        try:
            # Here we're are consciously violating Django's warning about not interacting with DB in AppConfig.ready
            # We know what we're doing, have considered a couple of other approaches and discussed it in great length:
            # https://github.com/edx/ecommerce/pull/630#discussion-diff-58026881
            # TODO: This was causing an issue with running migrations from scratch
            # on a sandbox. We need to fix this before uncommenting.
            # http://jenkins.edx.org:8080/job/ansible-provision/6495/console
            # validate_configuration()
            pass
        except OperationalError:
            log.exception(self.OPERATIONAL_ERROR_MESSAGE)

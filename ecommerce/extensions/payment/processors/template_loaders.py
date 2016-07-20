"""
Payment processor aware template loaders.
"""
import os

from django.conf import ImproperlyConfigured, settings
from django.core.exceptions import SuspiciousFileOperation
from django.template.loaders.filesystem import Loader as FilesystemLoader
from django.utils._os import safe_join

from path import Path

from threadlocals.threadlocals import get_current_request

from ecommerce.extensions.payment.helpers import get_processor_class


class PaymentProcessorTemplateLoader(FilesystemLoader):
    """
    Filesystem Template loaders to pickup templates from payment_processor directory based on the current site.
    """
    is_usable = True
    _accepts_engine_in_init = True

    def get_template_sources(self, template_name, template_dirs=None):
        """
        Returns the absolute paths to "template_name", when appended to each
        directory in "template_dirs". Any paths that don't lie inside one of the
        template dirs are excluded from the result set, for security reasons.
        """
        if not template_dirs:
            template_dirs = self.engine.dirs
        payment_processor_dirs = get_payment_processor_template_sources()

        # append payment processor dirs to the beginning so templates are looked up inside payment processor dir first
        if isinstance(payment_processor_dirs, list):
            template_dirs = payment_processor_dirs + template_dirs

        for template_dir in template_dirs:
            try:
                yield safe_join(template_dir, template_name)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                pass


def get_payment_processor_template_sources():
    """
    Return template sources for the given payment processor and if request object is None (this would be the
    case for management commands) return template sources for all payment processors.
    """
    request = get_current_request()
    if request:
        # template is being accessed by a view, so return templates sources for current payment processors
        payment_processors = request.site.siteconfiguration.get_payment_processors()
        processor_names = [name for name, __ in payment_processors.iteritems()]
    else:
        # if request object is not present, then this method is being called inside a management
        # command and return all theme template sources for compression
        all_processors = [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]
        processor_names = {processor.NAME for processor in all_processors}

    return get_template_dirs_for_payment_processors(processor_names)


def get_template_dirs_for_payment_processors(payment_processor_names):
    template_dirs = []
    for payment_processor_name in payment_processor_names:
        base_dir = get_base_dir(payment_processor_name)
        template_dirs += [
            Path(base_dir) / payment_processor_name,
            Path(base_dir) / payment_processor_name / 'oscar'
        ]

    return template_dirs


def get_base_dir(payment_processor_name, suppress_error=False):
    """
    Returns absolute path to the directory that contains the given payment processor template overrides.

    Args:
        payment_processor_name (str): payment processor template override directory name to get base path for
        suppress_error (bool): if True function will return None if template override directory is not found
                               instead of raising an error
    Returns:
        (str): Base directory that contains the given theme
    """
    base_dirs = get_payment_processor_template_dirs()
    for base_dir in base_dirs:
        # Return base_dir if it contains a directory with the given payment_processor_name
        if payment_processor_name in next(os.walk(base_dir))[1]:
            return base_dir

    if suppress_error:
        return None

    raise ValueError(
        "Payment processor overrides for '{payment_processor}' not found in any of the following dirs:,\n{dirs}".format(
            payment_processor=payment_processor_name,
            dirs=base_dirs,
        ))


def get_payment_processor_template_dirs():
    """
    Return a list of all directories that contain payment processor template overrides.

    Raises:
        ImproperlyConfigured - exception is raised if
            1 - PAYMENT_PROCESSOR_TEMPLATE_DIRS is not a list of strings
            2 - PAYMENT_PROCESSOR_TEMPLATE_DIRS is not an absolute path
            3 - path specified by PAYMENT_PROCESSOR_TEMPLATE_DIRS does not exist

    Example:
        >> get_payment_processor_template_dirs()
        ['/edx/app/ecommerce/ecommerce/templates/payment_processors']

    Returns:
         (list): list of payment processor template base directories
    """
    dirs = settings.PAYMENT_PROCESSOR_TEMPLATE_DIRS

    if not isinstance(dirs, list):
        raise ImproperlyConfigured("PAYMENT_PROCESSOR_TEMPLATE_DIRS must be a list.")

    template_dirs = []
    for directory in dirs:
        if not isinstance(directory, basestring):
            raise ImproperlyConfigured("PAYMENT_PROCESSOR_TEMPLATE_DIRS must contain only strings.")
        if not directory.startswith("/"):
            raise ImproperlyConfigured("PAYMENT_PROCESSOR_TEMPLATE_DIRS must contain only absolute paths.")
        if not os.path.isdir(directory):
            raise ImproperlyConfigured("PAYMENT_PROCESSOR_TEMPLATE_DIRS must contain valid paths.")

        template_dirs += Path(directory)

    return template_dirs

"""
Payment processor aware template loaders.
"""
import os

from django.apps import apps
from django.core.exceptions import SuspiciousFileOperation
from django.template.loaders.app_directories import Loader as AppDirectoriesLoader
from django.utils import lru_cache
from django.utils._os import safe_join, upath

from threadlocals.threadlocals import get_current_request


class PaymentProcessorTemplateLoader(AppDirectoriesLoader):
    """
    Template loader which looks for templates in payment processor app directories for
    the payment processors configured for the current site.
    """
    is_usable = True

    def get_template_sources(self, template_name, template_dirs=None):
        """
        Returns the absolute paths to "template_name", when appended to each
        directory in "template_dirs". Any paths that don't lie inside one of the
        template dirs are excluded from the result set, for security reasons.
        """
        request = get_current_request()
        if request:
            if not template_dirs:
                template_dirs = []
                payment_processors = request.site.siteconfiguration.get_payment_processors()
                for name, __ in payment_processors.iteritems():
                    template_dirs += list(get_app_template_dirs('templates', name))
                    template_dirs += list(get_app_template_dirs('templates/oscar', name))
            for template_dir in template_dirs:
                try:
                    yield safe_join(template_dir, template_name)
                except SuspiciousFileOperation:
                    # The joined path was located outside of this template_dir
                    # (it might be inside another one, so this isn't fatal).
                    pass


@lru_cache.lru_cache()
def get_app_template_dirs(dirname, app_label=None):
    """
    Return an iterable of paths of directories to load app templates from.

    dirname is the name of the subdirectory containing templates inside
    installed applications.

    Providing the app_label parameter will limit the returned directory paths
    to those that exist within the app which has an AppConfig.label that matches
    the given app_label.
    """
    template_dirs = []
    for app_config in apps.get_app_configs():
        if not app_config.path or (app_label and app_label != app_config.label):
            continue
        template_dir = os.path.join(app_config.path, dirname)
        if os.path.isdir(template_dir):
            template_dirs.append(upath(template_dir))
    # Immutable return value because it will be cached and shared by callers.
    return tuple(template_dirs)

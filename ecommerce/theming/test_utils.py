"""
Test helpers for Comprehensive Theming.
"""


import re
from functools import wraps

from django.contrib.sites.models import Site
from django.core.management import call_command
from mock import patch

from .models import SiteTheme


def with_comprehensive_theme(theme_dir_name):
    """
    A decorator to run a test with a comprehensive theming enabled.
    Arguments:
        theme_dir_name (str): directory name of the site for which we want comprehensive theming enabled.
    """
    # This decorator creates Site and SiteTheme models for given domain
    def _decorator(func):  # pylint: disable=missing-docstring
        @wraps(func)
        def _decorated(*args, **kwargs):  # pylint: disable=missing-docstring
            # make a domain name out of directory name
            domain = "{theme_dir_name}.org".format(theme_dir_name=re.sub(r"\.org$", "", theme_dir_name))
            site, __ = Site.objects.get_or_create(domain=domain, name=domain)
            site_theme, __ = SiteTheme.objects.get_or_create(site=site, theme_dir_name=theme_dir_name)
            with patch('ecommerce.theming.helpers.get_current_site_theme',
                       return_value=site_theme):
                return func(*args, **kwargs)
        return _decorated
    return _decorator


def compile_sass():
    """
    Call update assets command to compile system and theme sass.
    """
    # Compile system and theme sass files
    call_command('update_assets', '--skip-collect')

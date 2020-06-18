"""
Core logic for Comprehensive Theming.
"""


from django.conf import settings

from ecommerce.theming.helpers import get_themes


def enable_theming():
    """
        Add directories and relevant paths to settings for comprehensive theming.
    """
    for theme in get_themes():
        locale_dir = theme.path / "conf" / "locale"
        if locale_dir.isdir():
            settings.LOCALE_PATHS = (locale_dir, ) + settings.LOCALE_PATHS

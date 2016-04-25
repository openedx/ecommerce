"""
Core logic for Comprehensive Theming.
"""
from django.conf import settings
from path import Path

from ecommerce.theming.helpers import get_themes


def enable_theming(themes_dir):
    """
    Add directories and relevant paths to settings for comprehensive theming.

    Args:
        themes_dir (str): path to base theme directory
    """
    if isinstance(themes_dir, basestring):
        themes_dir = Path(themes_dir)

    for theme in get_themes(themes_dir):
        locale_dir = themes_dir / theme.theme_dir / "conf" / "locale"
        if locale_dir.isdir():
            settings.LOCALE_PATHS = (locale_dir, ) + settings.LOCALE_PATHS

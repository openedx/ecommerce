"""
    Helpers for accessing comprehensive theming related variables.
"""
import os

from django.conf import settings, ImproperlyConfigured
from django.core.cache import cache

import waffle
from path import Path
from threadlocals.threadlocals import get_current_request


def get_current_site():
    """
    Return current site.

    Returns:
         (django.contrib.sites.models.Site): current site
    """
    request = get_current_request()
    if not request:
        return None
    return getattr(request, 'site', None)


def is_comprehensive_theming_enabled():
    """
    Returns boolean indicating whether comprehensive theming functionality is enabled or disabled.

    Example:
        >> is_comprehensive_theming_enabled()
        True

    Returns:
         (bool): True if comprehensive theming is enabled else False
    """
    if not settings.ENABLE_COMPREHENSIVE_THEMING:
        # Return False if theming is disabled
        return False

    # return False if theming is disabled on runtime and function is called during request processing
    if bool(get_current_request()):
        # check if theming is disabled on runtime
        if waffle.switch_is_active(settings.DISABLE_THEMING_ON_RUNTIME_SWITCH):
            # function called in request processing and theming is disabled on runtime
            return False

    # Theming is enabled
    return True


def get_site_theme_cache_key(site):
    """
    Return cache key for the given site.

    Example:
        >> site = Site(domain='red-theme.org', name='Red Theme')
        >> get_site_theme_cache_key(site)
        'theming.site.red-theme.org'

    Parameters:
        site (django.contrib.sites.models.Site): site where key needs to generated
    Returns:
        (str): a key to be used as cache key
    """
    cache_key = "theming.site.{domain}".format(
        domain=site.domain
    )
    return cache_key


def cache_site_theme_dir(site, theme_dir):
    """
    Cache site's theme directory.

    Example:
        >> site = Site(domain='red-theme.org', name='Red Theme')
        >> cache_site_theme_dir(site, 'red-theme')

    Parameters:
        site (django.contrib.sites.models.Site): site for to cache
        theme_dir (str): theme directory for the given site
    """
    cache.set(get_site_theme_cache_key(site), theme_dir, settings.THEME_CACHE_TIMEOUT)


def get_current_theme_template_dirs():
    """
    Returns template directories for the current theme.

    Example:
        >> get_current_theme_template_dirs()
        [
            '/edx/app/ecommerce/ecommerce/themes/red-theme/templates/',
            '/edx/app/ecommerce/ecommerce/themes/red-theme/templates/oscar/',
        ]

    Returns:
        (list): list of directories containing theme templates.
    """
    site_theme_dir = get_theme_dir()
    if not site_theme_dir:
        return None

    template_paths = [
        site_theme_dir / 'templates',
        site_theme_dir / 'templates' / 'oscar',
    ]
    return template_paths


def get_all_theme_template_dirs():
    """
    Returns template directories for all the themes.

    Example:
        >> get_all_theme_template_dirs()
        [
            '/edx/app/ecommerce/ecommerce/themes/red-theme/templates/',
            '/edx/app/ecommerce/ecommerce/themes/red-theme/templates/oscar/',
        ]

    Returns:
        (list): list of directories containing theme templates.
    """
    themes = get_themes()
    template_paths = list()

    for theme in themes:
        template_paths.extend(
            [
                theme.path / 'templates',
                theme.path / 'templates' / 'oscar',
            ],
        )
    return template_paths


def get_theme_dir():
    """
    Return absolute directory for the current theme.

    Example:
        >> get_theme_dir()
        '/edx/app/ecommerce/ecommerce/themes/red-theme/'

    Returns:
         (Path): absolute directory for the current theme
    """
    site = get_current_site()

    if not is_comprehensive_theming_enabled():
        return None

    site_theme = site and site.themes.first()
    theme_dir = getattr(site_theme, "theme_dir_name") if site_theme else None

    if theme_dir:
        themes_dir = get_base_themes_dir()

        return Path(themes_dir) / theme_dir
    else:
        return None


def get_base_themes_dir():
    """
    Return base directory that contains all the themes.

    Raises:
        ImproperlyConfigured - exception is raised if
            1 - COMPREHENSIVE_THEME_DIR is not a string
            2 - COMPREHENSIVE_THEME_DIR is not an absolute path
            3 - path specified by COMPREHENSIVE_THEME_DIR does not exist

    Example:
        >> get_base_themes_dir()
        '/edx/app/ecommerce/ecommerce/themes'

    Returns:
         (Path): Base theme directory path
    """
    themes_dir = settings.COMPREHENSIVE_THEME_DIR

    if not isinstance(themes_dir, basestring):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIR must be a string.")
    if not themes_dir.startswith("/"):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIR must be an absolute path to themes dir.")
    if not os.path.isdir(themes_dir):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIR must be a valid path.")

    return Path(themes_dir)


def get_current_site_theme_dir():
    """
    Return theme directory for the current site.

    Example:
        >> get_current_site_theme_dir()
        'red-theme'

    Returns:
         (str): theme directory for current site
    """
    site = get_current_site()
    if not site:
        return None
    site_theme_dir = cache.get(get_site_theme_cache_key(site))

    # if site theme dir is not in cache and comprehensive theming is enabled then pull it from db.
    if not site_theme_dir and is_comprehensive_theming_enabled():
        site_theme = site.themes.first()  # pylint: disable=no-member
        if site_theme:
            site_theme_dir = site_theme.theme_dir_name
            cache_site_theme_dir(site, site_theme_dir)
    return site_theme_dir


def get_themes(themes_dir=None):
    """
    get a list of all themes known to the system.
    Args:
        themes_dir (str): (Optional) Path to themes base directory
    Returns:
        list of themes known to the system.
    """
    if not is_comprehensive_theming_enabled():
        return []

    themes_dir = Path(themes_dir) if themes_dir else get_base_themes_dir()
    # pick only directories and discard files in themes directory
    theme_names = []
    if themes_dir:
        theme_names = [_dir for _dir in os.listdir(themes_dir) if is_theme_dir(themes_dir / _dir)]

    return [Theme(name, name) for name in theme_names]


def is_theme_dir(_dir):
    """
    Returns true if given dir contains theme overrides.
    A theme dir must have subdirectory 'static' or 'templates' or both.

    Args:
        _dir: directory path to check for a theme

    Returns:
        Returns true if given dir is a theme directory.
    """
    theme_sub_directories = {'static', 'templates'}
    return bool(os.path.isdir(_dir) and theme_sub_directories.intersection(os.listdir(_dir)))


class Theme(object):
    """
    class to encapsulate theme related information.
    """
    name = ''
    theme_dir = ''

    def __init__(self, name='', theme_dir=''):
        """
        init method for Theme
        Args:
            name: name if the theme
            theme_dir: directory name of the theme
        """
        self.name = name
        self.theme_dir = theme_dir

    def __eq__(self, other):
        """
        Returns True if given theme is same as the self
        Args:
            other: Theme object to compare with self

        Returns:
            (bool) True if two themes are the same else False
        """
        return (self.theme_dir, self.path) == (other.theme_dir, other.path)

    def __hash__(self):
        return hash((self.theme_dir, self.path))

    def __unicode__(self):
        return u"<Theme: {name} at '{path}'>".format(name=self.name, path=self.path)

    def __repr__(self):
        return self.__unicode__()

    @property
    def path(self):
        return Path(get_base_themes_dir()) / self.theme_dir

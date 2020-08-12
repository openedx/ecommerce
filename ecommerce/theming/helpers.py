"""
    Helpers for accessing comprehensive theming related variables.
"""


import logging
import os

import waffle
from django.conf import ImproperlyConfigured, settings
from path import Path
from threadlocals.threadlocals import get_current_request

logger = logging.getLogger(__name__)


def get_current_site_theme():
    """
    Return current site theme object. Returns None if theming is disabled.

    Returns:
         (ecommerce.theming.models.SiteTheme): site theme object for the current site.
    """
    # Return None if theming is disabled
    if not is_comprehensive_theming_enabled():
        return None

    request = get_current_request()
    if not request:
        return None
    return getattr(request, 'site_theme', None)


def get_current_theme():
    """
    Return current theme object. Returns None if theming is disabled.

    Returns:
         (ecommerce.theming.helpers.Theme): theme object for the current theme.
    """
    # Return None if theming is disabled
    if not is_comprehensive_theming_enabled():
        return None

    site_theme = get_current_site_theme()
    if not site_theme:
        return None
    try:
        return Theme(
            name=site_theme.theme_dir_name,
            theme_dir_name=site_theme.theme_dir_name,
            themes_base_dir=get_theme_base_dir(site_theme.theme_dir_name),
        )
    except ValueError as e:
        # Log exception message and return None, so that open source theme is used instead
        logger.exception('Theme not found in any of the themes dirs. [%s]', e)
        return None


def get_theme_base_dir(theme_dir_name, suppress_error=False):
    """
    Returns absolute path to the directory that contains the given theme.

    Args:
        theme_dir_name (str): theme directory name to get base path for
        suppress_error (bool): if True function will return None if theme is not found instead of raising an error
    Returns:
        (str): Base directory that contains the given theme
    """
    for themes_dir in get_theme_base_dirs():
        if theme_dir_name in (_dir for _dir in os.listdir(themes_dir) if is_theme_dir(themes_dir / _dir)):
            return themes_dir

    if suppress_error:
        return None

    raise ValueError(
        "Theme '{theme}' not found in any of the following themes dirs, \nTheme dirs: \n{dir}".format(
            theme=theme_dir_name,
            dir=get_theme_base_dirs(),
        ))


def is_comprehensive_theming_enabled():
    """
    Returns boolean indicating whether theming is enabled or disabled.

    Example:
        >> is_comprehensive_theming_enabled()
        True

    Returns:
         (bool): True if theming is enabled else False
    """

    # Return False if theming is disabled via Django settings
    if not settings.ENABLE_COMPREHENSIVE_THEMING:
        return False

    # Return False if we're currently processing a request and theming is disabled via runtime switch
    if bool(get_current_request()) and waffle.switch_is_active(settings.DISABLE_THEMING_ON_RUNTIME_SWITCH):
        return False

    # Return True indicating theming is enabled
    return True


def get_all_theme_template_dirs():
    """
    Return a list of all template directories, for all the themes.

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


def get_theme_base_dirs():
    """
    Return a list of all directories that contain themes.

    Raises:
        ImproperlyConfigured - exception is raised if
            1 - COMPREHENSIVE_THEME_DIRS is not a string
            2 - COMPREHENSIVE_THEME_DIRS is not an absolute path
            3 - path specified by COMPREHENSIVE_THEME_DIRS does not exist

    Example:
        >> get_theme_base_dirs()
        ['/edx/app/ecommerce/ecommerce/themes']

    Returns:
         (list): list of theme base directories
    """
    theme_dirs = settings.COMPREHENSIVE_THEME_DIRS

    if not isinstance(theme_dirs, list):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIRS must be a list.")
    if not all([isinstance(theme_dir, str) for theme_dir in theme_dirs]):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIRS must contain only strings.")
    if not all([theme_dir.startswith("/") for theme_dir in theme_dirs]):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIRS must contain only absolute paths to themes dirs.")
    if not all([os.path.isdir(theme_dir) for theme_dir in theme_dirs]):
        raise ImproperlyConfigured("COMPREHENSIVE_THEME_DIRS must contain valid paths.")

    return [Path(theme_dir) for theme_dir in theme_dirs]


def get_themes(themes_dir=None):
    """
    Return a list of all themes known to the system.
    If themes_dir is given then return only the themes residing inside that directory.

    Args:
        themes_dir (str): (Optional) Path to themes base directory
    Returns:
        list of themes known to the system.
    """
    if not is_comprehensive_theming_enabled():
        return []

    themes_dirs = [Path(themes_dir)] if themes_dir else get_theme_base_dirs()
    # pick only directories and discard files in themes directory
    themes = []
    for tdir in themes_dirs:
        themes.extend([Theme(name, name, tdir) for name in get_theme_dirs(tdir)])

    return themes


def get_theme_dirs(themes_dir=None):
    """
    Return all theme dirs in given dir.
    """
    return [_dir for _dir in os.listdir(themes_dir) if is_theme_dir(themes_dir / _dir)]


def is_theme_dir(_dir):
    """
    Returns true if given dir is a theme directory, returns False otherwise.
    A theme dir must have subdirectory 'static' or 'templates' or both.

    Args:
        _dir: directory path to check for a theme

    Returns:
        Returns true if given dir is a theme directory.
    """
    theme_sub_directories = {'static', 'templates'}
    return bool(os.path.isdir(_dir) and theme_sub_directories.intersection(os.listdir(_dir)))


class Theme:
    """
    class to encapsulate theme related information.
    """
    name = ''
    theme_dir_name = ''

    def __init__(self, name='', theme_dir_name='', themes_base_dir=None):
        """
        init method for Theme
        Args:
            name: name if the theme
            theme_dir_name: directory name of the theme
            themes_base_dir: directory path of the folder that contains the theme
        """
        self.name = name
        self.theme_dir_name = theme_dir_name
        self.themes_base_dir = themes_base_dir

    def __eq__(self, other):
        """
        Returns True if given theme is same as the self
        Args:
            other: Theme object to compare with self

        Returns:
            (bool) True if two themes are the same else False
        """
        return (self.theme_dir_name, self.path) == (other.theme_dir_name, other.path)

    def __hash__(self):
        return hash((self.theme_dir_name, self.path))

    def __str__(self):
        return u"<Theme: {name} at '{path}'>".format(name=self.name, path=self.path)

    def __repr__(self):
        return self.__str__()

    @property
    def path(self):
        return Path(self.themes_base_dir) / self.theme_dir_name

    @property
    def template_dirs(self):
        return [
            self.path / 'templates',
            self.path / 'templates' / 'oscar',
        ]

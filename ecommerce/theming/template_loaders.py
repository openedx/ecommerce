"""
Theming aware template loaders.
"""


from django.template.loaders.filesystem import Loader
from threadlocals.threadlocals import get_current_request

from ecommerce.theming.helpers import get_all_theme_template_dirs, get_current_theme


class ThemeTemplateLoader(Loader):
    """
    Filesystem Template loaders to pickup templates from theme directory based on the current site.
    """
    def get_dirs(self):
        dirs = super(ThemeTemplateLoader, self).get_dirs()
        theme_dirs = []

        if get_current_request():
            # If the template is being loaded in a request, prepend the current theme's template directories
            # so the theme's templates take precedence.
            theme = get_current_theme()

            if theme:
                theme_dirs = theme.template_dirs
        else:
            # If we are outside of a request, we are most likely running the compress management command, in which
            # case we should load all directories for all themes.
            theme_dirs = get_all_theme_template_dirs()

        return theme_dirs + dirs

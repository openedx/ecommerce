"""
This file contains django compressor related functions.
"""
from ecommerce.theming.helpers import get_themes
from ecommerce.theming.storage import ThemeStorage


def offline_context():
    """
    offline context for compress management command, offline_context function iterates
    through all applied themes and returns a separate context for each theme.
    """

    for theme in get_themes():
        main_css = ThemeStorage(prefix=theme.theme_dir).url("css/base/main.css")
        swagger_css = ThemeStorage(prefix=theme.theme_dir).url("css/base/edx-swagger.css")

        yield {
            'main_css': main_css,
            'swagger_css': swagger_css,
        }

    yield {
        'main_css': ThemeStorage().url("css/base/main.css"),
        'swagger_css': ThemeStorage().url("css/base/edx-swagger.css"),
    }

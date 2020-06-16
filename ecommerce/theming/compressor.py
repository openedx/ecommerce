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
    main_css_path = "css/base/main.css"

    for theme in get_themes():
        main_css = ThemeStorage(prefix=theme.theme_dir_name).url(main_css_path)

        yield {
            'main_css': main_css,
        }

    yield {
        'main_css': ThemeStorage().url(main_css_path),
    }

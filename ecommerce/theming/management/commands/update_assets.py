"""
Managements for asset compilation and collection.
"""
import datetime
import logging

import sass
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from path import Path

from ecommerce.theming.helpers import get_theme_base_dirs, get_themes, is_comprehensive_theming_enabled

logger = logging.getLogger(__name__)

SYSTEM_SASS_PATHS = [
    # to resolve @import, we need to first look in 'sass/partials' then 'sass/base' and finally in "sass" dirs
    # "sass" dir does not contain any scss files yet, but can be used to place scss files that can not be overridden
    # by themes and contain only variable definitions (meaning, do not need to be compiled into css).
    Path("ecommerce/static/sass/partials"),
    Path("ecommerce/static/sass/base"),
    Path("ecommerce/static/sass"),
]


class Command(BaseCommand):
    """
    Compile and collect assets.
    """

    help = 'Compile and collect assets'

    # NOTE (CCB): This allows us to compile static assets in Docker containers without database access.
    requires_system_checks = False

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def add_arguments(self, parser):
        """
            Add arguments for update_assets command.

            Args:
                parser (django.core.management.base.CommandParser): parsed for parsing command line arguments.
        """

        # Named (optional) arguments
        parser.add_argument(
            '--themes',
            type=str,
            nargs='+',
            default=["all"],
            help="List of themes whose sass need to compiled. Or 'no'/'all' to compile for no/all themes.",
        )

        parser.add_argument(
            '--output-style',
            type=str,
            dest='output_style',
            default='nested',
            help='Coding style for compiled sass (default="nested").',
        )

        parser.add_argument(
            '--skip-system',
            dest='system',
            action='store_false',
            default=True,
            help='Skip system sass compilation.',
        )
        parser.add_argument(
            '--enable-source-comments',
            dest='source_comments',
            action='store_true',
            default=False,
            help="Add source comments in compiled sass.",
        )

        parser.add_argument(
            '--skip-collect',
            dest='collect',
            action='store_false',
            default=True,
            help="Skip collection of static assets.",
        )

    @staticmethod
    def parse_arguments(*args, **options):  # pylint: disable=unused-argument
        """
        Parse and validate arguments for update_assets command.

        Args:
            *args: Positional arguments passed to the update_assets command
            **options: optional arguments passed to the update_assets command
        Returns:
            A tuple containing parsed values for themes, system, source comments and output style.
            1. themes (list): list of Theme objects
            2. system (bool): True if system sass need to be compiled, False otherwise
            3. source_comments (bool): True if source comments need to be included in output, False otherwise
            4. output_style (str): Coding style for compiled css files.
        """
        given_themes = options.get("themes", ["all"])
        output_style = options.get("output_style", "nested")
        system = options.get("system", True)
        source_comments = options.get("source_comments", False)
        collect = options.get("collect", True)

        available_themes = {t.theme_dir_name: t for t in get_themes()}

        if 'no' in given_themes or 'all' in given_themes:
            # Raise error if 'all' or 'no' is present and theme names are also given.
            if len(given_themes) > 1:
                raise CommandError("Invalid themes value, It must either be 'all' or 'no' or list of themes.")
        # Raise error if any of the given theme name is invalid
        # (theme name would be invalid if it does not exist in themes directory)
        elif (not set(given_themes).issubset(list(available_themes.keys()))) and is_comprehensive_theming_enabled():
            raise CommandError(
                "Given themes '{invalid_themes}' do not exist inside themes directory '{themes_dir}'".format(
                    invalid_themes=", ".join(set(given_themes) - set(available_themes.keys())),
                    themes_dir=get_theme_base_dirs(),
                ),
            )

        if "all" in given_themes:
            themes = get_themes()
        elif "no" in given_themes:
            themes = []
        else:
            # convert theme names to Theme objects
            themes = [available_themes.get(theme) for theme in given_themes]

        return themes, system, source_comments, output_style, collect

    def handle(self, *args, **options):
        """
        Handle update_assets command.
        """
        logger.info("Sass compilation started.")
        info = []

        themes, system, source_comments, output_style, collect = self.parse_arguments(*args, **options)

        if not is_comprehensive_theming_enabled():
            themes = []
            logger.info("Skipping theme sass compilation as theming is disabled.")

        for sass_dir in get_sass_directories(themes, system):
            result = compile_sass(
                sass_source_dir=sass_dir['sass_source_dir'],
                css_destination_dir=sass_dir['css_destination_dir'],
                lookup_paths=sass_dir['lookup_paths'],
                output_style=output_style,
                source_comments=source_comments,
            )
            info.append(result)

        logger.info("Sass compilation completed.")

        for sass_dir, css_dir, duration in info:
            logger.info(">> %s -> %s in %ss", sass_dir, css_dir, duration)
        logger.info("\n")

        if collect and not settings.DEBUG:
            # Collect static assets
            collect_assets()


def get_sass_directories(themes, system=True):
    """
    Get sass directories for given themes and system.

    Args:
        themes (list): list of all the themes for whom to fetch sass directories
        system (bool): boolean showing whether to get sass directories for the system or not.

    Returns:
        List of all sass directories that need to be compiled.
    """
    applicable_dirs = list()

    if system:
        applicable_dirs.append({
            "sass_source_dir": Path("ecommerce/static/sass/base"),
            "css_destination_dir": Path("ecommerce/static/css/base"),
            "lookup_paths": SYSTEM_SASS_PATHS,
        })

    applicable_dirs.extend(get_theme_sass_directories(themes))
    return applicable_dirs


def get_theme_sass_directories(themes):
    """
    Get sass directories for given themes and system.

    Args:
        themes (list): list of all the themes for whom to fetch sass directories

    Returns:
        List of all sass directories that need to be compiled for the given themes.

    """
    applicable_dirs = list()

    for theme in themes:
        # compile sass with theme overrides and place them in theme dir.
        applicable_dirs.append({
            "sass_source_dir": Path("ecommerce/static/sass/base"),
            "css_destination_dir": theme.path / "static" / "css" / "base",
            "lookup_paths": [theme.path / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS,
        })

        # Now, override existing css with any other sass overrides
        theme_sass_dir = theme.path / "static" / "sass" / "base"
        if theme_sass_dir.isdir():
            applicable_dirs.append({
                "sass_source_dir": theme.path / "static" / "sass" / "base",
                "css_destination_dir": theme.path / "static" / "css" / "base",
                "lookup_paths": [theme.path / "static" / "sass" / "partials"] + SYSTEM_SASS_PATHS,
            })

    return applicable_dirs


def compile_sass(sass_source_dir, css_destination_dir, lookup_paths, **kwargs):
    """
    Compile given sass files.

    Exceptions:
        ValueError: Raised if sass source directory does not exist.

    Args:
        sass_source_dir (path.Path): directory path containing source sass files
        css_destination_dir (path.Path): directory path where compiled css files would be placed
        lookup_paths (list): a list of all paths that need to be consulted to resolve @imports from sass

    Returns:
        A tuple containing sass source dir, css destination dir and duration of sass compilation process
    """
    output_style = kwargs.get('output_style', 'compressed')
    source_comments = kwargs.get('source_comments', False)
    start = datetime.datetime.now()

    if not sass_source_dir.isdir():
        logger.warning("Sass dir '%s' does not exist.", sass_source_dir)
        raise ValueError("Sass dir '{dir}' must be a valid directory.".format(dir=sass_source_dir))
    if not css_destination_dir.isdir():
        # If css destination directory does not exist, then create one
        css_destination_dir.mkdir_p()

    sass.compile(
        dirname=(sass_source_dir, css_destination_dir),
        include_paths=lookup_paths,
        source_comments=source_comments,
        output_style=output_style,
    )
    duration = datetime.datetime.now() - start

    return sass_source_dir, css_destination_dir, duration


def collect_assets():
    """
    Collect static assets.
    """
    logger.info("\t\tStarted collecting static assets.")
    call_command("collectstatic")
    logger.info("\t\tFinished collecting static assets.")

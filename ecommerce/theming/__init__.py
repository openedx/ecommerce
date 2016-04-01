"""
This app contains theming and branding logic for ecommerce. It contains necessary components, overrides and helpers
needed for the theming to work properly.

Components:
    Template Loaders (ecommerce.theming.template_loaders.ThemeTemplateLoader):
        Theming aware template loaders, this loader will first look in template directories of current theme and then
        it will look at system template dirs.
        ThemeFilesFinder looks for static assets inside theme directories. It creates separate storage for each theme.

    Static Files Finders (ecommerce.theming.finders.ThemeFilesFinder):
        Theming aware Static files finder.

        During collectstatic run it utilizes all of these storages to fetch static assets for each theme.
        Since, storage saves each theme asset in its own sub directory
        (i.e. {STATIC_ROOT}/red-theme/images/default-logo.png) and also creates asset url with theme name
        prefixed (i.e. /static/red-theme/images/default-logo.png), during post-processing and development mode,
        finder will know which theme asset is being accessed (judging from the prefix), and will use the
        corresponding storage to access the file.
        If prefix is not a theme name (we know all theme names via get_themes helper), ThemeFilesFinder will know
        that a system asset is being accessed.

    Static Files Storage (ecommerce.theming.storage.ThemeStorage):
        Theming aware static storage.
        During collectstatic run it will take all themed assets and place theme in theme subdirectory (e.g. red-theme)
        inside static directory. All system assets are saved normally. e.g. 'red-theme' assets will be stored in
        '{STATIC_ROOT}/red-theme/' and system assets will be stored in '{STATIC_ROOT}/'.

        While serving static assets it prefixes asset url with theme name (e.g. 'red-theme'), only if assets
        is overridden by theme. e.g. if red-theme provides 'images/default-logo.png' then corresponding url
        will be "/static/red-theme/images/default-logo.png" and if red-theme does not provide 'images/default-logo.png'
        then corresponding url will be "/static/images/default-logo.png".

Models:
    Site theme (ecommerce.theming.models.SiteTheme):
        Site theme model to store theme info for a given site.

        Fields:
            site (ForeignKey): Foreign Key field pointing to django Site model
            theme_dir_name (CharField): Contains directory name for any site's theme (e.g. 'red-theme')
"""
default_app_config = "ecommerce.theming.apps.ThemeAppConfig"

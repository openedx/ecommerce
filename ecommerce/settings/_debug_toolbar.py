# DJANGO DEBUG TOOLBAR CONFIGURATION
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': (lambda __: True),
    'DISABLE_PANELS': (
        'debug_toolbar.panels.template.TemplateDebugPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
    ),
}
# END DJANGO DEBUG TOOLBAR CONFIGURATION

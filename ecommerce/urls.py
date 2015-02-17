import os

from django.conf import settings
from django.conf.urls import patterns, url, include
from django.conf.urls.static import static


# Uncomment the next two lines to enable the admin
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Uncomment the next line to enable the admin
    # url(r'^admin/', include(admin.site.urls)),

    # Heartbeat page
    url(r'^health$', include('health.urls')),
)

if settings.DEBUG and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT)

if settings.DEBUG:  # pragma: no cover
    urlpatterns += patterns(
        '',
        url(r'^403/$', 'django.views.defaults.permission_denied'),
        url(r'^404/$', 'django.views.defaults.page_not_found'),
        url(r'^500/$', 'django.views.defaults.server_error'),
    )

    if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
        import debug_toolbar  # pylint: disable=import-error

        urlpatterns += patterns(
            '',
            url(r'^__debug__/', include(debug_toolbar.urls)),
        )

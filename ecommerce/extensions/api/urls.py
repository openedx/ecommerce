from django.conf.urls import patterns, url, include


urlpatterns = patterns(
    '',
    url(r'^v2/', include('ecommerce.extensions.api.v2.urls', namespace='v2')),
)

from django.conf.urls import url, patterns

from health import views


urlpatterns = patterns('',
    url(r'^$', views.health, name='health'),
)

from django.conf.urls import url, patterns

from ecommerce.health import views


urlpatterns = patterns(
    '',
    url(r'^$', views.health, name='health'),
)

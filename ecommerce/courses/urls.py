from django.conf import settings
from django.conf.urls import patterns, url

from ecommerce.courses import views

urlpatterns = patterns(
    '',
    url(r'^$', views.CourseListView.as_view(), name='list'),
    url(r'^migrate/$', views.CourseMigrationView.as_view(), name='migrate'),
    url(r'^{}/$'.format(settings.COURSE_ID_PATTERN), views.CourseDetailView.as_view(), name='detail'),
)

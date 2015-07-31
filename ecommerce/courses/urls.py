from django.conf.urls import patterns, url

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.courses import views


urlpatterns = patterns(
    '',
    url(r'^$', views.CourseListView.as_view(), name='list'),
    url(r'^migrate/$', views.CourseMigrationView.as_view(), name='migrate'),
    url(r'^{}/$'.format(COURSE_ID_PATTERN), views.CourseDetailView.as_view(), name='detail'),
)

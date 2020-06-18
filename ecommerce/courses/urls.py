

from django.conf.urls import url

from ecommerce.courses import views

urlpatterns = [
    url(r'^migrate/$', views.CourseMigrationView.as_view(), name='migrate'),
    url(r'^convert_course/$', views.ConvertCourseView.as_view(), name='convert_course'),

    # Declare all paths above this line to avoid dropping into the Course Admin Tool (which does its own routing)
    url(r'^(.*)$', views.CourseAppView.as_view(), name='app'),
]

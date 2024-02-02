

from django.urls import path, re_path

from ecommerce.courses import views

urlpatterns = [
    path('migrate/', views.CourseMigrationView.as_view(), name='migrate'),
    path('convert_course/', views.ConvertCourseView.as_view(), name='convert_course'),

    # Declare all paths above this line to avoid dropping into the Course Admin Tool (which does its own routing)
    re_path(r'^(.*)$', views.CourseAppView.as_view(), name='app'),
]

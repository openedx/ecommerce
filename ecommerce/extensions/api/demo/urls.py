from django.conf.urls import url

from ecommerce.extensions.api.demo import views

urlpatterns = [
    url(r'^courses/$', views.CourseListView.as_view()),
    url(r'^courses/(?P<pk>[\w.-]+)/recommendations/$', views.CourseRecommendationView.as_view()),
    url(r'^users/$', views.UserListView.as_view()),
    url(r'^users/(?P<username>[\w.-]+)/enrollments/$', views.UserEnrollmentsView.as_view()),
    url(r'^users/(?P<username>[\w.-]+)/recommendations/$', views.UserRecommendationView.as_view()),
]

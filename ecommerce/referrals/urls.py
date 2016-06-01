from django.conf.urls import url

from ecommerce.referrals import views

urlpatterns = [
    url(
        r'^affiliates/(?P<affiliate_partner>\w+)/validation_report/$',
        views.ValidationReportCsvView.as_view(),
        name='validation-report'
    ),
]

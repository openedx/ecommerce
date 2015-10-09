from django.http import HttpResponse


def EnrollmentCodes(request):
    return HttpResponse('Codes')


def NewEnrollmentCode(request):
    return HttpResponse('New code')

from rest_framework.pagination import PageNumberPagination


class LargeResultsSetPagination(PageNumberPagination):
    page_size = 100

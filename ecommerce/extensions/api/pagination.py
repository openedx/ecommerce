from rest_framework import pagination


class PageNumberPagination(pagination.PageNumberPagination):
    page_size_query_param = 'page_size'

    # NOTE (CCB): This is a hack, necessary until the frontend
    # can properly follow our paginated lists.
    max_page_size = 10000

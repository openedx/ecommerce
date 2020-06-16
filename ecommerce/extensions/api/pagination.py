

from edx_rest_framework_extensions.paginators import DefaultPagination
from rest_framework_datatables.pagination import DatatablesPageNumberPagination


class PageNumberPagination(DatatablesPageNumberPagination):
    page_size_query_param = 'page_size'

    # NOTE (CCB): This is a hack, necessary until the frontend
    # can properly follow our paginated lists.
    max_page_size = 10000


class DatatablesDefaultPagination(DefaultPagination, PageNumberPagination):
    """ Default Pagination for Datatables. """

from crum import CurrentRequestUserMiddleware


class PatchedCurrentRequestUserMiddleware(CurrentRequestUserMiddleware):
    """
    Patched version of CurrentRequestUserMiddleware.

    This is required because when ecommerce code raises a `Http404`
    exception, django-crum runs its `process_exception` and clears
    the request from the thread local variable, breaking code that
    relies on it.
    """
    def process_exception(self, request, exception):
        """
        Does nothing on `process_exception` as opposed of the
        original behavior of removing the request from the
        thread local variables.
        """

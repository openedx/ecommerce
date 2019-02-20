"""
Taken from https://github.com/escodebar/django-rest-framework-rules/blob/master/rest_framework_rules/decorators.py.
"""
from __future__ import absolute_import


def permission_required(*permissions, **decorator_kwargs):

    def decorator(view):
        def wrapped_view(self, request, *args, **kwargs):

            fn = decorator_kwargs.pop('fn', None)
            if callable(fn):
                obj = fn(request, *args, **kwargs)
            else:
                obj = fn

            missing_permissions = [perm for perm in permissions
                                   if not request.user.has_perm(perm, obj)]
            if any(missing_permissions):
                # raises a permission denied exception causing a 403 response
                self.permission_denied(
                    request,
                    message=('Missing: {}'
                             .format(', '.join(missing_permissions)))
                )

            return view(self, request, *args, **kwargs)
        return wrapped_view
    return decorator
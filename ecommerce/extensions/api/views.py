from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext as _
from rest_framework.permissions import AllowAny
from rest_framework.renderers import CoreJSONRenderer
from rest_framework.response import Response
from rest_framework.schemas import SchemaGenerator
from rest_framework.views import APIView
from rest_framework_swagger.renderers import OpenAPIRenderer, SwaggerUIRenderer


class SwaggerSchemaView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [
        CoreJSONRenderer,
        OpenAPIRenderer,
        SwaggerUIRenderer,
    ]

    exclude_from_schema = True

    def get(self, request):
        generator = SchemaGenerator(title='Ecommerce API')
        schema = generator.get_schema(request=request)

        if not schema:
            # get_schema() uses the same permissions check as the API endpoints.
            # If we don't get a schema document back, it means the user is not
            # authenticated or doesn't have permission to access the API.
            # api_docs_permission_denied_handler() handles both of these cases.
            return api_docs_permission_denied_handler(request)

        return Response(schema)


def api_docs_permission_denied_handler(request):
    """
    Permission denied handler for calls to the API documentation.

    Args:
        request (Request): Original request to the view the documentation

    Raises:
        PermissionDenied: The user is not authorized to view the API documentation.

    Returns:
        HttpResponseRedirect: Redirect to the login page if the user is not logged in. After a
            successful login, the user will be redirected back to the original path.
    """
    if request.user and request.user.is_authenticated():
        raise PermissionDenied(_('You are not permitted to access the API documentation.'))

    login_url = '{path}?next={next}'.format(path=reverse('login'), next=request.path)
    return redirect(login_url, permanent=False)

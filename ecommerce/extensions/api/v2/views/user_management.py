

import logging

from django.apps import apps
from django.db import transaction
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.views import APIView

from ecommerce.extensions.api.permissions import CanReplaceUsername

log = logging.getLogger(__name__)


class UsernameReplacementView(APIView):
    """
    WARNING: This API is only meant to be used as part of a larger job that
    updates usernames across all services. DO NOT run this alone or users will
    not match across the system and things will be broken. This API should be
    called from the LMS endpoint which verifies uniqueness of the username
    first.

    API will recieve a list of current usernames and their new username.
    """

    authentication_classes = (JwtAuthentication, )
    permission_classes = (permissions.IsAuthenticated, CanReplaceUsername)

    def post(self, request):
        """
        **POST Parameters**

        A POST request must include the following parameter.

        * username_mappings: Required. A list of objects that map the current username (key)
          to the new username (value)
            {
                "username_mappings": [
                    {"current_username_1": "new_username_1"},
                    {"current_username_2": "new_username_2"}
                ]
            }

        **POST Response Values**

        As long as data validation passes, the request will return a 200 with a new mapping
        of old usernames (key) to new username (value)

        {
            "successful_replacements": [
                {"old_username_1": "new_username_1"}
            ],
            "failed_replacements": [
                {"old_username_2": "new_username_2"}
            ]
        }

        """

        # (model_name, column_name)
        MODELS_WITH_USERNAME = (
            ('core.user', 'username'),
            ('payment.sdncheckfailure', 'username')
        )

        username_mappings = request.data.get("username_mappings")
        replacement_locations = self._load_models(MODELS_WITH_USERNAME)

        if not self._has_valid_schema(username_mappings):
            raise ValidationError("Request data does not match schema")

        successful_replacements, failed_replacements = [], []

        for username_pair in username_mappings:
            current_username = list(username_pair.keys())[0]
            new_username = list(username_pair.values())[0]
            successfully_replaced = self._replace_username_for_all_models(
                current_username,
                new_username,
                replacement_locations
            )
            if successfully_replaced:
                successful_replacements.append({current_username: new_username})
            else:
                failed_replacements.append({current_username: new_username})  # pragma: no cover
        return Response(
            status=status.HTTP_200_OK,
            data={
                "successful_replacements": successful_replacements,
                "failed_replacements": failed_replacements
            }
        )

    def _load_models(self, models_with_fields):
        """ Takes tuples that contain a model path and returns the list with a loaded version of the model """
        replacement_locations = [(apps.get_model(model), column) for (model, column) in models_with_fields]
        return replacement_locations

    def _has_valid_schema(self, post_data):
        """ Verifies the data is a list of objects with a single key:value pair """
        if not isinstance(post_data, list):
            return False
        for obj in post_data:
            if not (isinstance(obj, dict) and len(obj) == 1):
                return False
        return True

    def _replace_username_for_all_models(self, current_username, new_username, replacement_locations):
        """
        Replaces current_username with new_username for all (model, column) pairs in replacement locations.
        Returns if it was successful or not. Usernames that don't exist in this service will be treated as
        a success because no work needs to be done changing their username.
        """
        try:
            with transaction.atomic():
                num_rows_changed = 0
                for (model, column) in replacement_locations:
                    num_rows_changed += model.objects.filter(
                        **{column: current_username}
                    ).update(
                        **{column: new_username}
                    )
        except Exception as exc:   # pragma: no cover pylint: disable=broad-except
            log.exception(
                "Unable to change username from %s to %s. Failed on table %s because %s",
                current_username,
                new_username,
                model.__class__.__name__,
                exc,
            )
            return False  # pragma: no cover
        if num_rows_changed == 0:
            log.info(
                "Unable to change username from %s to %s because %s doesn't exist.",
                current_username,
                new_username,
                current_username,
            )
        else:
            log.info(
                "Successfully changed username from %s to %s.",
                current_username,
                new_username,
            )
        return True

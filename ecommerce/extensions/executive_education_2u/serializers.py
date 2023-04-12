from rest_framework import serializers


class UserDetailsSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    date_of_birth = serializers.CharField()
    mobile_phone = serializers.CharField(required=False)
    work_experience = serializers.CharField(required=False)
    education_highest_level = serializers.CharField(required=False)


class AddressSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    address_line1 = serializers.CharField(required=False)
    address_line2 = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    state_code = serializers.CharField(required=False)
    country = serializers.CharField(required=False)
    country_code = serializers.CharField(required=False)


class CheckoutActionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    sku = serializers.CharField()
    address = AddressSerializer(required=False)
    user_details = UserDetailsSerializer()
    terms_accepted_at = serializers.CharField()
    data_share_consent = serializers.BooleanField(required=False)

from rest_framework import serializers


class UserDetailsSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    date_of_birth = serializers.CharField()


class AddressSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    address_line1 = serializers.CharField()
    city = serializers.CharField()
    postal_code = serializers.CharField()
    state = serializers.CharField()
    state_code = serializers.CharField()
    country = serializers.CharField()
    country_code = serializers.CharField()


class CheckoutActionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    sku = serializers.CharField()
    address = AddressSerializer()
    user_details = UserDetailsSerializer()
    terms_accepted_at = serializers.CharField()

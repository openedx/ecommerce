from rest_framework import serializers


class CourseEntitlementInfoSerializer(serializers.Serializer):
    course_uuid = serializers.CharField()
    mode = serializers.CharField()
    sku = serializers.CharField()

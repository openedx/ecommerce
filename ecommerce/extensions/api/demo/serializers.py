from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class CourseSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class RecommendedCourseSerializer(CourseSerializer):
    weight = serializers.IntegerField()

from django.utils.functional import cached_property
from py2neo import Graph
from rest_framework import generics
from rest_framework.response import Response

from ecommerce.extensions.api.demo import serializers

NEO4J_URI = 'http://neo4j:edx@localhost:7474/db/data/'


class GraphMixin(object):
    @cached_property
    def graph(self):
        return Graph(NEO4J_URI)

    @property
    def run(self):
        return self.graph.run


class UserListView(GraphMixin, generics.ListAPIView):
    serializer_class = serializers.UserSerializer

    def get_queryset(self):
        username = self.request.GET.get('q')

        if not username:
            return Response({'error': 'You must supply a value for the q parameter.'}, status=400)

        username = username.lower()
        statement = "MATCH (student:Student) " \
                    "WHERE student.username =~ '(?i){username}.*' " \
                    "RETURN student.id AS id, student.username AS username;".format(username=username)
        results = self.run.execute(statement)
        return results


class UserRecommendationView(GraphMixin, generics.ListAPIView):
    serializer_class = serializers.RecommendedCourseSerializer
    pagination_class = None

    def get_queryset(self):
        username = self.kwargs['username'].lower()

        statement = "MATCH (student:Student {{username: \"{username}\"}}) " \
                    "MATCH (student)-[:ENROLLED_IN]->(course_run)<-[:ENROLLED_IN]-(other_student)-[:ENROLLED_IN]-(other_run)-[:IS_RUN_OF]->(recommendations) " \
                    "WHERE NOT(student = other_student) " \
                    "RETURN COUNT(*) AS weight, recommendations.id AS id, recommendations.name AS name " \
                    "ORDER BY weight DESC, id, name " \
                    "LIMIT 20".format(username=username)

        results = self.run(statement)
        return results


class UserEnrollmentsView(GraphMixin, generics.ListAPIView):
    serializer_class = serializers.CourseSerializer
    pagination_class = None

    def get_queryset(self):
        username = self.kwargs['username'].lower()

        statement = "MATCH (student:Student {{username: \"{username}\"}}) " \
                    "MATCH (student)-[:ENROLLED_IN]-(course_run)-[:IS_RUN_OF]->(courses) " \
                    "RETURN courses.id AS id, courses.name AS name".format(username=username)

        results = self.run(statement)
        return results


class CourseListView(GraphMixin, generics.ListAPIView):
    serializer_class = serializers.CourseSerializer

    def get_queryset(self):
        query = self.request.GET.get('q')
        statement = "MATCH (course:Course) RETURN course.id AS id, course.name AS name;"

        if query:
            statement = "MATCH (course:Course) " \
                        "WHERE course.id =~ '(?i).*{q}.*' OR course.name =~ '.*{q}.*' " \
                        "RETURN course.id AS id, course.name AS name".format(q=query)

        results = self.run(statement)
        return list(results)


class CourseRecommendationView(GraphMixin, generics.ListAPIView):
    serializer_class = serializers.RecommendedCourseSerializer
    pagination_class = None

    def get_queryset(self):
        course_id = self.kwargs['pk'].lower()

        statement = "MATCH (course:Course {{id: '{course_id}'}}) " \
                    "MATCH (course)-[:IS_RUN_OF]-(course_run)-[:ENROLLED_IN]-(student)-[:ENROLLED_IN]-(other_run)-[:IS_RUN_OF]->(recommendations) " \
                    "RETURN COUNT(*) AS weight, recommendations.id AS id, recommendations.name AS name " \
                    "ORDER BY weight DESC, id, name " \
                    "LIMIT 20".format(course_id=course_id)

        results = self.run(statement)
        return results

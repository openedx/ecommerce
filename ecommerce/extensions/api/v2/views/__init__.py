from rest_framework import mixins, viewsets


class NonDestroyableModelViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    pass

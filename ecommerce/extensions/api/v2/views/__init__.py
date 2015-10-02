from rest_framework import viewsets, mixins


class NonDestroyableModelViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    pass

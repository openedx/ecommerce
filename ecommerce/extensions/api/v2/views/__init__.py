from __future__ import absolute_import

from rest_framework import mixins, viewsets


class NonDestroyableModelViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    """ None Destroyable Model View Set. """

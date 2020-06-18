# NOTE (CCB): These functions are copied from oscar.apps.offer.custom due to a bug
# detailed at https://github.com/django-oscar/django-oscar/issues/2345. This file
# should be removed after the fix for the bug is released.
# TODO: Issue above is fixed; we need to upgrade to django-oscar==1.5 and this can be removed.
# (https://github.com/django-oscar/django-oscar/commit/38367f9ca854cd21eaf19a174f24b59a0e65cf79)


from oscar.core.loading import get_model

Condition = get_model('offer', 'Condition')


def class_path(klass):
    return '%s.%s' % (klass.__module__, klass.__name__)


def create_condition(condition_class, **kwargs):
    """
    Create a custom condition instance
    """
    return Condition.objects.create(
        proxy_class=class_path(condition_class), **kwargs)

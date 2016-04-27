"""Utilities for end-to-end tests."""


def str2bool(s):
    s = unicode(s)
    return s.lower() in (u'yes', u'true', u't', u'1')

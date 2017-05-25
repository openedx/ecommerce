from django.conf.urls import url
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from ecommerce.courses.models import Course


class CourseAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'name', 'site',)
    search_fields = ('id', 'name', 'site', )
    list_filter = ('site', )

    def get_urls(self):
        """Returns the additional urls used by the Reversion admin."""
        urls = super(SimpleHistoryAdmin, self).get_urls()  # pylint: disable=bad-super-call
        admin_site = self.admin_site
        opts = self.model._meta  # pylint: disable=protected-access
        try:
            info = opts.app_label, opts.model_name
        except AttributeError:  # Django < 1.7
            info = opts.app_label, opts.module_name
        history_urls = [
            # Note: We use a custom URL pattern to match against course IDs.
            url("^(.+)/history/([^/]+)/$",
                admin_site.admin_view(self.history_form_view),
                name='%s_%s_simple_history' % info),
        ]
        return history_urls + urls


admin.site.register(Course, CourseAdmin)

from django.contrib import admin

from ecommerce.courses.models import Course


class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'site',)
    search_fields = ('id', 'name', 'site', )
    list_filter = ('site', )


admin.site.register(Course, CourseAdmin)

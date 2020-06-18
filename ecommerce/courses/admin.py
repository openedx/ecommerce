

from django.contrib import admin

from ecommerce.courses.models import Course


class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'partner',)
    search_fields = ('id', 'name', 'partner', )
    list_filter = ('partner', )


admin.site.register(Course, CourseAdmin)

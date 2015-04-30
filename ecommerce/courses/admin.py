from django.contrib import admin

from ecommerce.courses.models import Course


class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)


admin.site.register(Course, CourseAdmin)

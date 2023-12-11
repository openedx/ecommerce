

from django.contrib import admin

from ecommerce.courses.models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'partner',)
    search_fields = ('id', 'name', 'partner', )
    list_filter = ('partner', )

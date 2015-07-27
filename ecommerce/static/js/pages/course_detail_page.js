require([
        'models/course_model',
        'views/course_detail_view'
    ],
    function (CourseModel, CourseDetailView) {
        'use strict';

        var $el = $('.course-detail-view'),
            course = new CourseModel({id: $el.data('course-id')});
        new CourseDetailView({el: $el[0], model: course});
        course.fetch();
    }
);

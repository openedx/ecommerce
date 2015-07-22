require([
        'collections/course_collection',
        'views/course_list_view'
    ],
    function (CourseCollection, CourseListView) {

        return new CourseListView({
            collection: new CourseCollection()
        });

    }
);

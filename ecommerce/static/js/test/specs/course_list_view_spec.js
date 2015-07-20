define([
        'jquery',
        'views/course_list_view',
        'collections/course_collection'
       ],
       function ($, CourseListView, CourseCollection) {

           describe('course list view', function () {

                var view,
                    collection,
                    defaultCourses,
                    renderInterval;

                beforeEach(function (done) {

                    defaultCourses = {
                        "id": "edX/DemoX.1/2014",
                        "name": "DemoX",
                        "last_edited": "2015-06-16T19:14:34Z"
                    },
                    {
                        "id": "edX/victor101/Victor_s_Test_Course",
                        "name": "Victor's Test Course",
                        "last_edited": "2015-06-16T19:42:55Z"
                    };

                    collection = new CourseCollection();

                    spyOn(collection, 'fetch').and.callFake(function () {
                        collection.set(defaultCourses);
                    });

                    // Set up the environment
                    setFixtures('<div id="course-list-view"></div>');

                    view = new CourseListView({
                        collection: collection
                    });

                    // Wait till the DOM is rendered before continuing
                    renderInterval = setInterval(function () {
                        if (view.$el.html()) {
                            clearInterval(renderInterval);
                            done();
                        }
                    }, 100);

                });

                it('should change the default filter placeholder to a custom string', function () {
                    expect(view.$el.find('#courseTable_filter input').attr('placeholder')).toBe('Filter by org or course ID');
                });

                it('should adjust the style of the filter textbox', function () {

                    var $tableInput = view.$el.find('#courseTable_filter input');

                    expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                    expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();

                });

                it('should populate the table based on the course collection', function () {

                    var table = $('#courseTable').DataTable();
                        tableData = table.data();

                        expect(tableData.data().length).toBe(collection.length);

                });

            });
    }
);

define([
        'jquery',
        'views/course_list_view',
        'collections/course_collection'
    ],
    function ($,
              CourseListView,
              CourseCollection) {
        'use strict';

        describe('course list view', function () {
            var view,
                collection,
                courses = [
                    {
                        id: 'edX/DemoX.1/2014',
                        name: 'DemoX',
                        last_edited: '2015-06-16T19:14:34Z',
                        type: 'honor'
                    },
                    {
                        id: 'edX/victor101/Victor_s_Test_Course',
                        name: 'Victor\'s Test Course',
                        last_edited: '2015-06-16T19:42:55Z',
                        type: 'professional'
                    }
                ];

            beforeEach(function () {
                collection = new CourseCollection();
                collection.set(courses);

                view = new CourseListView({collection: collection}).render();
            });

            it('should change the default filter placeholder to a custom string', function () {
                expect(view.$el.find('#courseTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should adjust the style of the filter textbox', function () {
                var $tableInput = view.$el.find('#courseTable_filter input');

                expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();
            });

            it('should populate the table based on the course collection', function () {
                var tableData = view.$el.find('#courseTable').DataTable().data();
                expect(tableData.data().length).toBe(collection.length);
            });

        });
    }
);

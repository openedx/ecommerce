define([
    'jquery',
    'views/course_list_view',
    'mock-ajax'
],
    function($, CourseListView) {
        'use strict';

        describe('course list view', function() {
            var view,
                collection,
                courses = {
                    "recordsTotal": 2,
                    "recordsFiltered": 2,
                    "data": [
                        {
                            "id": "course-v1:edX+DemoX+Demo_Course_89",
                            "name": "AAJNCJVJKE",
                            "type": "verified",
                            "last_edited": "2019-04-12T14:19:11Z"
                        }, {
                            "id": "course-v1:edX+DemoX+Demo_Course_222",
                            "name": "AAYRYEBQMT",
                            "type": "verified",
                            "last_edited": "2019-04-12T14:19:29Z"
                        }
                    ],
                    "draw": 1
                };

            beforeEach(function() {
                jasmine.Ajax.install();
                view = new CourseListView().render();
            });

            afterEach(function() {
                jasmine.Ajax.uninstall();
            });

            it('should change the default filter placeholder to a custom string', function() {
                expect(view.$el.find('#courseTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should adjust the style of the filter textbox', function() {
                var $tableInput = view.$el.find('#courseTable_filter input');

                expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();
            });

            it('should populate the table based on the course collection', function() {
                jasmine.Ajax.stubRequest('/api/v2/courses/?format=datatables').andReturn({
                    "responseJSON": courses,
                    "status": 200
                });
                var tableData = view.$el.find('#courseTable').DataTable().data();
                expect(tableData.data().length).toBe(courses.data.length);
            });
        });
    }
);

define([
    'jquery',
    'views/course_list_view'
],
    function($, CourseListView) {
        'use strict';

        describe('course list view', function() {
            var view,
                courses = {
                    recordsTotal: 2,
                    recordsFiltered: 2,
                    data: [
                        {
                            id: 'course-v1:edX+TextX+Test_Course_01',
                            name: 'Test Course 1',
                            type: 'verified',
                            last_edited: new Date()
                        },
                        {
                            id: 'course-v1:edX+TestX+Test_Course_02',
                            name: 'Test Course 2',
                            type: 'verified',
                            last_edited: new Date()
                        }
                    ],
                    draw: 1
                };

            beforeEach(function() {
                spyOn($, 'ajax').and.callFake(function(params) {
                    params.success(courses);
                });
                view = new CourseListView().render();
            });

            it('should change the default filter placeholder to a custom string', function() {
                expect(view.$el.find('#courseTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should adjust the style of the filter textbox', function() {
                var $tableInput = view.$el.find('#courseTable_filter input');

                expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();
            });

            it('should populate the table based on the course api response', function() {
                var tableData = view.$el.find('#courseTable').DataTable().data();
                expect(tableData.data().length).toBe(courses.data.length);
            });
        });
    }
);

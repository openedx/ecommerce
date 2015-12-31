define([
        'jquery',
        'views/course_create_edit_view',
        'views/alert_view',
        'models/course_model'
    ],
    function ($,
              CourseCreateEditView,
              AlertView,
              Course) {
        'use strict';

        describe('course create view', function () {
            var view,
                model;

            beforeEach(function () {
                model = new Course();
                view = new CourseCreateEditView({ model: model, editing: false }).render();
            });

            it('should throw an error if submitted with blank fields', function () {
                var errorHTML = '<strong>Error!</strong> You must complete all required fields.';
                view.formView.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });

        });
    }
);

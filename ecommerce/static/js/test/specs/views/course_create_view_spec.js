define([
    'jquery',
    'underscore',
    'views/course_create_edit_view',
    'views/alert_view',
    'test/spec-utils',
    'models/course_model',
    'test/custom-matchers'
],
    function($,
             _,
             CourseCreateEditView,
             AlertView,
             SpecUtils,
             Course) {
        'use strict';

        describe('course create view', function() {
            var view,
                model;

            beforeEach(function() {
                model = new Course();
                view = new CourseCreateEditView({model: model, editing: false}).render();
            });

            it('should throw an error if submitted with blank fields', function() {
                var errorHTML = '<strong></strong> Please complete all required fields.';
                view.formView.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });
            it('select a course type message is removed', function() {
                expect(view.$el.find('.course-types input[type=radio]:checked').length).toEqual(0);
                expect(view.$el.find('.course-seat.empty').hasClass('hidden')).toBe(false);
                expect(view.$el.find('.course-types input[type=radio]').length).toEqual(5);

                view.model.set('type', 'credit');
                expect(view.$el.find('.course-types input[type=radio]:checked').length).toEqual(1);
                expect(view.$el.find('.course-seat.empty').hasClass('hidden')).toBe(true);
            });
        });
    }
);

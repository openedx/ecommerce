define([
    'jquery',
    'models/course_model',
    'views/course_form_view'
],
    function($,
              Course,
              CourseFormView) {
        'use strict';

        var model, view;

        beforeEach(function() {
            model = new Course();
            view = new CourseFormView({model: model});
        });

        describe('course form view', function() {
            describe('cleanHonorCode', function() {
                it('should always return a boolean', function() {
                    expect(view.cleanBooleanValue('false')).toEqual(false);
                    expect(view.cleanBooleanValue('true')).toEqual(true);
                });
            });

            describe('getActiveCourseTypes', function() {
                it('should return expected course types', function() {
                    view.model.set('type', 'audit');
                    expect(view.getActiveCourseTypes()).toEqual(['audit', 'verified', 'credit']);

                    view.model.set('type', 'verified');
                    expect(view.getActiveCourseTypes()).toEqual(['verified', 'credit']);

                    view.model.set('type', 'verified-only');
                    expect(view.getActiveCourseTypes()).toEqual(['verified-only', 'credit']);

                    view.model.set('type', 'professional');
                    expect(view.getActiveCourseTypes()).toEqual(['professional']);

                    view.model.set('type', 'credit');
                    expect(view.getActiveCourseTypes()).toEqual(['credit']);

                    view.model.set('type', 'default');
                    expect(view.getActiveCourseTypes()).toEqual(
                        ['audit', 'verified', 'verified-only', 'professional', 'credit']);
                });
            });
        });
    }
);

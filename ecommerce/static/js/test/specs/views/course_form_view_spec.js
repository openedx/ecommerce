define([
        'jquery',
        'models/course_model',
        'views/course_form_view'
    ],
    function ($,
              Course,
              CourseFormView) {
        'use strict';

        var model, view;

        beforeEach(function () {
            model = new Course();
            view = new CourseFormView({model: model});
        });

        describe('course form view', function () {
            describe('cleanHonorCode', function () {
                it('should always return a boolean', function () {
                    expect(view.cleanHonorMode('false')).toEqual(false);
                    expect(view.cleanHonorMode('true')).toEqual(true);
                });
            });

            describe('getActiveCourseTypes', function () {
                it('should return expected course types', function () {
                    view.model.set('type', 'audit');
                    expect(view.getActiveCourseTypes()).toEqual(['audit', 'verified', 'credit']);

                    view.model.set('type', 'verified');
                    expect(view.getActiveCourseTypes()).toEqual(['verified', 'credit']);

                    view.model.set('type', 'professional');
                    expect(view.getActiveCourseTypes()).toEqual(['professional']);

                    view.model.set('type', 'credit');
                    expect(view.getActiveCourseTypes()).toEqual(['credit']);

                    view.model.set('type', 'default');
                    expect(view.getActiveCourseTypes()).toEqual(['audit', 'verified', 'professional', 'credit']);
                });
            });

            describe('Bulk enrollment code tests', function() {
                it('should check enrollment code checkbox', function() {
                    view.$el.append('<input type="checkbox" name="bulk_enrollment_code">');
                    view.model.set('bulk_enrollment_code', true);
                    view.renderBulkEnrollmentCode();
                    expect(view.$('[name=bulk_enrollment_code]').prop('checked')).toBeTruthy();
                });

                it('should make an ajax call to site configuration', function() {
                    var mockAjaxData = {'results': [{
                            'enable_enrollment_codes': true,
                            'site': {
                                'domain': 'test.site.domain'
                            }
                        }]
                    };
                    spyOn($, 'ajax').and.callFake(function(options) {
                        options.success(mockAjaxData);
                    });
                    view.toggleDisabledBulkEnrollmentField();
                    expect($.ajax).toHaveBeenCalled();
                });
            });
        });
    }
);

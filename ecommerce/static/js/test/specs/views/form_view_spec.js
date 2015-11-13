define([
        'jquery',
        'backbone',
        'views/form_view'
    ],
    function ($,
              Backbone,
              FormView) {
        'use strict';

        describe('form view', function () {
            var view,
                TestModel,
                model;

            beforeEach(function () {
                TestModel = Backbone.Model.extend({ url: 'fake/url' });
                model = new TestModel();
                view = new FormView({ model: model });
                view.$el.prepend('<div class="alerts" tabindex="-1" aria-live="polite"></div>');
                view.render();
            });

            it('should throw an error if submitted with blank fields', function () {
                var errorHTML = '<strong>Error!</strong> Please complete all required fields.';
                spyOn(model, 'isValid').and.returnValue(false);
                view.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });

            it('should save model on submit', function () {
                spyOn(model, 'isValid').and.returnValue(true);
                spyOn(Backbone.history, 'navigate');
                spyOn(model, 'save').and.callFake(function (options) {
                    options.success({ id: 'fake_id' });
                    options.complete();
                });
                view.submit($.Event('click'));
                expect(model.save).toHaveBeenCalled();
                expect(Backbone.history.navigate).toHaveBeenCalled();
            });

            it('should call saveSuccess when model is successfully saved', function () {
                spyOn(view, 'saveSuccess');
                spyOn(model, 'isValid').and.returnValue(true);
                spyOn(model, 'save').and.callFake(function (options) {
                    options.success({ id: 'fake_id' });
                });
                view.submit($.Event('click'));
                expect(view.saveSuccess).toHaveBeenCalled();
            });

            it('should throw an error if saving the data fails', function () {
                var errorHTML = '<strong>Error!</strong> An error occurred while saving the data.',
                    errorObj;

                function testErrorResponse() {
                    view.submit($.Event('click'));
                    expect(model.save).toHaveBeenCalled();
                    expect(view.$el.find('.alert').length).toBe(1);
                    expect(view.$el.find('.alert').html()).toBe(errorHTML);
                }

                spyOn(model, 'isValid').and.returnValue(true);
                spyOn(model, 'save').and.callFake(function (options) {
                    options.error(model, errorObj);
                    options.complete();
                });

                errorObj = { responseText: 'Fake error!' };
                testErrorResponse();

                errorObj = { responseJSON: { error: 'An error occurred while saving the data.' }};
                testErrorResponse();
            });

        });
    }
);

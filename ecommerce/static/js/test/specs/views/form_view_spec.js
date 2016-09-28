define([
        'jquery',
        'backbone',
        'text!templates/_alert_div.html',
        'views/form_view'
    ],
    function ($,
              Backbone,
              AlertDivTemplate,
              FormView) {
        'use strict';

        describe('form view', function () {
            var view,
                TestModel,
                model,
                errorHTML,
                courseId;

            beforeEach(function () {
                TestModel = Backbone.Model.extend({ url: 'fake/url' });
                model = new TestModel();
                view = new FormView({ model: model });
                view.$el.prepend(AlertDivTemplate);
                view.render();
                courseId = 'course-v1:edX+DemoX+Demo_Course';
            });

            it('should throw an error if submitted with blank fields', function () {
                errorHTML = '<strong></strong> Please complete all required fields.';
                spyOn(model, 'isValid').and.returnValue(false);
                view.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });

            it('should save model on submit', function () {
                spyOn(model, 'isValid').and.returnValue(true);
                spyOn(Backbone.history, 'navigate');
                spyOn(model, 'save').and.callFake(function (attributes, options) {
                    options.success({ id: 'fake_id' });
                    options.complete();
                });
                view.submit($.Event('click'));
                expect(model.save).toHaveBeenCalled();
                expect(Backbone.history.navigate).toHaveBeenCalled();
            });

            it('should validate if course id is duplicate', function () {
                 var courseDataSuccess = {
                        id: courseId,
                        name: 'Demo Course',
                        type: 'audit'
                 },
                     redirected_url = '/courses/' + courseId,
                     html = '<a href="'+redirected_url+'"> Click here to view the existing course</a>';
                errorHTML = '<strong>Error!</strong> A course with the specified ID already exists.' + html;

                 //check the error msg is empty
                 expect(view.$el.find('.alert').length).toBe(0);

                 spyOn($, 'ajax').and.callFake( function (callback) {
                     //Check the success method of ajax
                     callback.success(courseDataSuccess);
                    });
                 view.checkCourseAlreadyExist(courseId);

                 expect(view.$el.find('.alert').length).toBe(1);
                 expect(view.$el.find('.alert').html()).toBe(errorHTML);
             });

            it('should not validate if course id is not duplicate', function () {
                 var errorResponse = {
                     status : 404
                 };

                 //check the error msg is empty
                 expect(view.$el.find('.alert').length).toBe(0);

                 //Check the failure method of ajax
                 spyOn($, 'ajax').and.callFake( function (callback) {
                     callback.error(errorResponse);
                    });
                 view.checkCourseAlreadyExist(courseId);
                 expect(view.$el.find('.alert').length).toBe(0);
             });

            it('should check ajax method has been called', function () {
                 var args;
                 spyOn($, 'ajax');
                 view.checkCourseAlreadyExist(courseId);

                 // $.ajax should have been called
                 expect($.ajax).toHaveBeenCalled();
                 args = $.ajax.calls.argsFor(0)[0];
                 expect(args.method).toEqual('get');
                 expect(args.url).toEqual('/api/v2/courses/'+courseId);
                 expect(args.contentType).toEqual('application/json');
             });

            it('should check validateCourseID method has been called' , function(){
                view.$el.prepend('<input type="text" class="form-control" name="id" ' +
                     'value = "course-v1:edX+DemoX+Demo_Course" >');
                var courseIdInput = $(view.el).find('input[name=id]');
                spyOn(view, 'checkCourseAlreadyExist');
                view.validateCourseID();
                courseIdInput.trigger('focusout');
                expect(view.checkCourseAlreadyExist).toHaveBeenCalled();
            });

            it('should call saveSuccess when model is successfully saved', function () {
                spyOn(view, 'saveSuccess');
                spyOn(model, 'isValid').and.returnValue(true);
                spyOn(model, 'save').and.callFake(function (attributes, options) {
                    options.success({ id: 'fake_id' });
                });
                view.submit($.Event('click'));
                expect(view.saveSuccess).toHaveBeenCalled();
            });

            it('should throw an error if saving the data fails', function () {
                var errorObj;
                errorHTML = '<strong>Error!</strong> An error occurred while saving the data.';

                function testErrorResponse() {
                    view.submit($.Event('click'));
                    expect(model.save).toHaveBeenCalled();
                    expect(view.$el.find('.alert').length).toBe(1);
                    expect(view.$el.find('.alert').html()).toBe(errorHTML);
                }

                spyOn(model, 'isValid').and.returnValue(true);
                spyOn(model, 'save').and.callFake(function (attributes, options) {
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

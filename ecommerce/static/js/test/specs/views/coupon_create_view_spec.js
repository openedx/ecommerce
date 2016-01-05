define([
        'jquery',
        'views/coupon_create_edit_view',
        'views/alert_view',
        'models/coupon_model'
    ],
    function ($,
              CouponCreateEditView,
              AlertView,
              Coupon) {
        'use strict';

        describe('coupon create view', function () {
            var view,
                model,
                courseData = {
                    id: 'course-v1:edX+DemoX+Demo_Course',
                    name: 'Demo Course',
                    type: 'verified',
                    products: [
                        {
                            id: 3,
                            product_class: 'Seat',
                            structure: 'child',
                            expires: null,
                            attribute_values: [
                                {
                                    name: 'certificate_type',
                                    value: 'verified'
                                }
                            ],
                            is_available_to_buy: true,
                            stockrecords: [
                                {
                                    id: 2,
                                    product: 3,
                                    partner: 1
                                }
                            ]
                        }
                    ]
                };


            beforeEach(function () {
                model = new Coupon();
                view = new CouponCreateEditView({ model: model, editing: false }).render();
                spyOn(model, 'save');
            });

            it('should throw an error if submitted with blank fields', function () {
                var errorHTML = '<strong>Error!</strong> You must complete all required fields.';
                view.formView.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });

            it('should submit form with valid fields', function () {
                jasmine.clock().install();
                view.$el.find('[name=title]').val('Test Enrollment').trigger('change');
                view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                view.$el.find('[name=client_username]').val('test_client').trigger('change');
                view.$el.find('[name=start_date]').val('2015-01-01T00:00').trigger('change');
                view.$el.find('[name=end_date]').val('2016-01-01T00:00').trigger('change');
                view.$el.find('[name=price]').val('100').trigger('change');
                spyOn($, 'ajax').and.callFake(function (options) {
                    options.success(courseData);
                });
                // inputing the course id will load the seat type options
                view.$el.find('[name=course_id]').val('course-v1:edX+DemoX+Demo_Course').trigger('input');
                // event is debounced, override _.now to trigger immediately
                spyOn(_, 'now').and.returnValue(Date.now() + 110);
                jasmine.clock().tick(110);
                view.formView.submit($.Event('click'));
                expect(model.isValid()).toBe(true);
                expect(model.save).toHaveBeenCalled();
                jasmine.clock().uninstall();
            });

        });
    }
);

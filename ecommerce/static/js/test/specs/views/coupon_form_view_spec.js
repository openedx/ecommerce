define([
        'jquery',
        'underscore',
        'views/coupon_form_view',
        'views/alert_view',
        'models/coupon_model',
        'test/mock_data/categories',
        'test/mock_data/coupons',
        'ecommerce'
    ],
    function ($,
              _,
              CouponFormView,
              AlertView,
              Coupon,
              Mock_Categories,
              Mock_Coupons,
              ecommerce) {
        'use strict';

        describe('coupon form view', function () {
            var view,
                model,
                courseData = Mock_Coupons.courseData;

            /**
              * Helper function to check if a form field is shown.
              */
            function visible(selector) {
                var formGroup = view.$el.find(selector).closest('.form-group');
                if (formGroup.length > 0) {
                    return !formGroup.hasClass('hidden');
                } else {
                    return false;
                }
            }

            beforeEach(function () {
                ecommerce.coupons = {
                    categories: Mock_Categories
                };
                model = new Coupon();
                view = new CouponFormView({ editing: false, model: model }).render();
            });

            describe('seat type dropdown', function () {

                var courseId = 'course-v1:edX+DemoX+Demo_Course',
                    seatType;

                beforeEach(function () {
                    jasmine.clock().install();
                    seatType = view.$el.find('[name=seat_type]');
                    spyOn($, 'ajax').and.callFake(function (options) {
                        options.success(courseData);
                    });
                    view.$el.find('[name=course_id]').val(courseId).trigger('input');
                    // event is debounced, override _.now to trigger immediately
                    spyOn(_, 'now').and.returnValue(Date.now() + 110);
                    jasmine.clock().tick(110);
                });

                afterEach(function () {
                    jasmine.clock().uninstall();
                });

                it('should fill seat type options from course ID', function () {
                    expect($.ajax).toHaveBeenCalled();
                    expect(seatType.children().length).toBe(2);
                    expect(seatType.children()[0].innerHTML).toBe('Verified');
                    expect(seatType.children()[1].innerHTML).toBe('Honor');
                });

                it('should set stock_record_ids from seat type', function () {
                    seatType.children()[0].selected = true;
                    seatType.trigger('change');
                    expect(model.get('stock_record_ids')).toEqual([2]);
                });
            });


            describe('enrollment code', function () {
                beforeEach(function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                });

                it('should show the price field', function () {
                    expect(visible('[name=price]')).toBe(true);
                });

                it('should hide discount and code fields', function () {
                    expect(visible('[name=benefit_value]')).toBe(false);
                    expect(visible('[name=code]')).toBe(false);
                });

                it('should show the quantity field only for single-use vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(visible('[name=quantity]')).toBe(true);
                    view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(visible('[name=quantity]')).toBe(false);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(visible('[name=quantity]')).toBe(false);
                });
            });

            describe('discount', function () {
                beforeEach(function () {
                    view.$el.find('[name=code_type]').val('discount').trigger('change');
                });

                it('should show the discount field', function () {
                    expect(visible('[name=benefit_value]')).toBe(true);
                });

                it('should indicate the benefit type', function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$el.find('.benefit-addon').html()).toBe('%');
                    view.$el.find('[name=benefit_type]').val('Fixed').trigger('change');
                    expect(view.$el.find('.benefit-addon').html()).toBe('$');
                });

                it('should toggle upper limit on the benefit value input', function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$el.find('[name="benefit_value"]').attr('max')).toBe('100');
                    view.$el.find('[name=benefit_type]').val('Fixed').trigger('change');
                    expect(view.$el.find('[name="benefit_value"]').attr('max')).toBe('');
                });

                it('should show the code field only for multi-use vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(visible('[name=code]')).toBe(false);
                    view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(visible('[name=code]')).toBe(true);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(visible('[name=code]')).toBe(true);
                });
            });

        });
    }
);

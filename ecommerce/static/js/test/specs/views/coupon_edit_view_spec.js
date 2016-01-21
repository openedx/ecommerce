define([
        'underscore.string',
        'utils/utils',
        'views/coupon_create_edit_view',
        'models/coupon_model'
    ],
    function (_s,
              Utils,
              CouponCreateEditView,
              Coupon) {

        'use strict';

        describe('course edit view', function () {
            var view,
                model,
                verifiedSeat = {
                    id: 9,
                    url: 'http://ecommerce.local:8002/api/v2/products/9/',
                    structure: 'child',
                    product_class: 'Seat',
                    title: 'Seat in edX Demonstration Course with verified certificate (and ID verification)',
                    price: '15.00',
                    expires: '2020-01-01T00:00:00Z',
                    attribute_values: [
                        {
                            name: 'certificate_type',
                            value: 'verified'
                        },
                        {
                            name: 'course_key',
                            value: 'edX/DemoX/Demo_Course'
                        },
                        {
                            name: 'id_verification_required',
                            value: true
                        }
                    ],
                    is_available_to_buy: true
                },
                data = {
                    'id': 10,
                    'title': 'Test Enrollment Code',
                    'coupon_type': 'Enrollment code',
                    'last_edited': [
                        'user',
                        '2016-01-15T07:26:22.926Z'
                    ],
                    'seats': [
                        verifiedSeat
                    ],
                    'client': 'Client Name',
                    'price': '100.00',
                    'vouchers': [
                        {
                            'id': 1,
                            'name': 'Test Enrollment Code',
                            'code': 'XP54BC4M',
                            'redeem_url': 'http://localhost:8002/coupons/offer/?code=XP54BC4M',
                            'usage': 'Single use',
                            'start_datetime': '2015-01-01T00:00:00Z',
                            'end_datetime': '2017-01-01T00:00:00Z',
                            'num_basket_additions': 0,
                            'num_orders': 0,
                            'total_discount': '0.00',
                            'date_created': '2015-12-23',
                            'offers': [
                                1
                            ],
                            'is_available_to_user': [
                                true,
                                ''
                            ],
                            'benefit': [
                                'Percentage',
                                100.0
                            ]
                        }
                    ]
                };

            beforeEach(function () {
                model = new Coupon(data);
                model.updateSeatData();
                model.updateVoucherData();
                view = new CouponCreateEditView({model: model, editing: true}).render();
            });

            it('should display coupon details in form fields', function () {
                var voucherType = view.$el.find('[name=voucher_type]');
                expect(view.$el.find('[name=title]').val()).toEqual(model.get('title'));
                expect(view.$el.find('[name=code_type]').val()).toEqual(model.get('code_type'));
                expect(view.$el.find('[name=start_date]').val()).toEqual(Utils.stripTimezone(model.get('start_date')));
                expect(view.$el.find('[name=end_date]').val()).toEqual(Utils.stripTimezone(model.get('end_date')));
                expect(voucherType.children().length).toBe(3);
                expect(voucherType.val()).toEqual(model.get('voucher_type'));
                expect(view.$el.find('[name=quantity]').val()).toEqual(model.get('quantity').toString());
                expect(view.$el.find('[name=client_username]').val()).toEqual(model.get('client'));
                expect(view.$el.find('[name=price]').val()).toEqual(model.get('price'));
                expect(view.$el.find('[name=course_id]').val()).toEqual(model.get('course_id'));
            });
        });
    }
);

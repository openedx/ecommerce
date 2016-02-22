define([
        'underscore.string',
        'utils/utils',
        'views/coupon_create_edit_view',
        'models/coupon_model',
        'views/coupon_form_view'
    ],
    function (_s,
              Utils,
              CouponCreateEditView,
              Coupon,
              CouponFormView) {

        'use strict';

        describe('coupons edit view', function () {
            var view,
                model,
                enrollment_code_data = {
                    'id': 4,
                    'title': 'TestWIthNote',
                    'coupon_type': 'Enrollment code',
                    'last_edited': [
                        'staff',
                        '2016-02-22T13:19:34.087Z'
                    ],
                    'seats': [
                        {
                            'id': 2,
                            'url': 'http://localhost:8002/api/v2/products/2/',
                            'structure': 'child',
                            'product_class': 'Seat',
                            'title': 'Seat in Test Course with verified certificate (and ID verification)',
                            'price': '100.00',
                            'expires': null,
                            'attribute_values': [
                                {
                                    'name': 'certificate_type',
                                    'value': 'verified'
                                },
                                {
                                    'name': 'course_key',
                                    'value': 'course-v1:edX+DemoX+Demo_Course'
                                },
                                {
                                    'name': 'id_verification_required',
                                    'value': true
                                }
                            ],
                            'is_available_to_buy': true,
                            'stockrecords': [
                                {
                                    'id': 1,
                                    'product': 2,
                                    'partner': 1,
                                    'partner_sku': '8CF08E5',
                                    'price_currency': 'USD',
                                    'price_excl_tax': '100.00'
                                }
                            ]
                        }
                    ],
                    'client': 'TestClient',
                    'price': '1000.00',
                    'category': {
                        'id': '4',
                        'children': [],
                        'path': '00020001',
                        'depth': 2,
                        'numchild': 0,
                        'name': 'Affiliate Promotion',
                        'description': '',
                        'image': null,
                        'slug': 'affiliate-promotion'
                    },
                    'attribute_values': [
                        {
                            'name': 'Coupon vouchers',
                            'value': [
                                {
                                    'id': 1,
                                    'name': 'TestWIthNote',
                                    'code': 'U3UDTMPEIPD67YKL',
                                    'redeem_url': 'http://localhost:8002/coupons/offer/?code=U3UDTMPEIPD67YKL',
                                    'usage': 'Single use',
                                    'start_datetime': '2016-01-01T00:00:00Z',
                                    'end_datetime': '2016-07-01T00:00:00Z',
                                    'num_basket_additions': 0,
                                    'num_orders': 0,
                                    'total_discount': '0.00',
                                    'date_created': '2016-02-22',
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
                        },
                        {
                            'name': 'Note',
                            'value': 'Some Note I dont Know'
                        }
                    ]
                },
                discount_code_data = {
                    'id': 4,
                    'title': 'TestWIthNote',
                    'coupon_type': 'Discount code',
                    'last_edited': [
                        'staff',
                        '2016-02-22T13:19:34.087Z'
                    ],
                    'seats': [
                        {
                            'id': 2,
                            'url': 'http://localhost:8002/api/v2/products/2/',
                            'structure': 'child',
                            'product_class': 'Seat',
                            'title': 'Seat in Test Course with verified certificate (and ID verification)',
                            'price': '100.00',
                            'expires': null,
                            'attribute_values': [
                                {
                                    'name': 'certificate_type',
                                    'value': 'verified'
                                },
                                {
                                    'name': 'course_key',
                                    'value': 'course-v1:edX+DemoX+Demo_Course'
                                },
                                {
                                    'name': 'id_verification_required',
                                    'value': true
                                }
                            ],
                            'is_available_to_buy': true,
                            'stockrecords': [
                                {
                                    'id': 1,
                                    'product': 2,
                                    'partner': 1,
                                    'partner_sku': '8CF08E5',
                                    'price_currency': 'USD',
                                    'price_excl_tax': '100.00'
                                }
                            ]
                        }
                    ],
                    'client': 'TestClient',
                    'price': '1000.00',
                    'category': {
                        'id': '4',
                        'children': [],
                        'path': '00020001',
                        'depth': 2,
                        'numchild': 0,
                        'name': 'Affiliate Promotion',
                        'description': '',
                        'image': null,
                        'slug': 'affiliate-promotion'
                    },
                    'attribute_values': [
                        {
                            'name': 'Coupon vouchers',
                            'value': [
                                {
                                    'id': 1,
                                    'name': 'TestWIthNote',
                                    'code': 'U3UDTMPEIPD67YKL',
                                    'redeem_url': 'http://localhost:8002/coupons/offer/?code=U3UDTMPEIPD67YKL',
                                    'usage': 'Single use',
                                    'start_datetime': '2016-01-01T00:00:00Z',
                                    'end_datetime': '2016-07-01T00:00:00Z',
                                    'num_basket_additions': 0,
                                    'num_orders': 0,
                                    'total_discount': '0.00',
                                    'date_created': '2016-02-22',
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
                        },
                        {
                            'name': 'Note',
                            'value': 'Some Note I dont Know'
                        }
                    ]
                },
                categoriesDropdownOptions = [
                    {
                        value: '4',
                        label: 'Affiliate Promotion',
                        selected: true
                    }
                ],
                mockedFetchedCategories = {
                    id: 3,
                    children: [
                        {
                            id: '4',
                            children: [],
                            path: '00020001',
                            depth: 2,
                            numchild: 0,
                            name: 'Affiliate Promotion',
                            description: '',
                            image: null,
                            slug: 'affiliate-promotion'
                        }
                    ]
                };

            describe('edit enrollment code', function () {
                beforeEach(function () {
                    spyOn(CouponFormView.prototype.couponCategoryCollection, 'fetch')
                        .and.returnValue(mockedFetchedCategories);
                    spyOn(CouponFormView.prototype, 'updateDropdown').and.callFake(function(){
                        this.categories = categoriesDropdownOptions;
                    });
                    model = new Coupon(enrollment_code_data);
                    model.updateSeatData();
                    model.updateVoucherData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display coupon details in form fields', function () {
                    var voucherType = view.$el.find('[name=voucher_type]'),
                        startDate = Utils.stripTimezone(model.get('start_date')),
                        endDate = Utils.stripTimezone(model.get('end_date'));
                    expect(view.$el.find('[name=title]').val()).toEqual(model.get('title'));
                    expect(view.$el.find('[name=code_type]').val()).toEqual('enrollment');
                    expect(view.$el.find('[name=start_date]').val()).toEqual(startDate);
                    expect(view.$el.find('[name=end_date]').val()).toEqual(endDate);
                    expect(voucherType.children().length).toBe(3);
                    expect(voucherType.val()).toEqual(model.get('voucher_type'));
                    expect(view.$el.find('[name=quantity]').val()).toEqual(model.get('quantity').toString());
                    expect(view.$el.find('[name=client_username]').val()).toEqual(model.get('client'));
                    expect(view.$el.find('[name=price]').val()).toEqual(model.get('price'));
                    expect(view.$el.find('[name=course_id]').val()).toEqual(model.get('course_id'));
                    expect(view.$el.find('[name=category]').val()).toEqual(model.get('category').id);
                    expect(view.$el.find('[name=note]').val()).toEqual(model.get('note'));
                });
            });

            describe('edit discount code', function () {
                beforeEach(function () {
                    spyOn(CouponFormView.prototype.couponCategoryCollection, 'fetch')
                        .and.returnValue(mockedFetchedCategories);
                    spyOn(CouponFormView.prototype, 'updateDropdown').and.callFake(function(){
                        this.categories = categoriesDropdownOptions;
                    });
                    model = new Coupon(discount_code_data);
                    model.updateSeatData();
                    model.updateVoucherData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display coupon details in form fields', function () {
                    var voucherType = view.$el.find('[name=voucher_type]'),
                        startDate = Utils.stripTimezone(model.get('start_date')),
                        endDate = Utils.stripTimezone(model.get('end_date'));
                    expect(view.$el.find('[name=title]').val()).toEqual(model.get('title'));
                    expect(view.$el.find('[name=code_type]').val()).toEqual('discount');
                    expect(view.$el.find('[name=start_date]').val()).toEqual(startDate);
                    expect(view.$el.find('[name=end_date]').val()).toEqual(endDate);
                    expect(voucherType.children().length).toBe(3);
                    expect(voucherType.val()).toEqual(model.get('voucher_type'));
                    expect(view.$el.find('[name=quantity]').val()).toEqual(model.get('quantity').toString());
                    expect(view.$el.find('[name=client_username]').val()).toEqual(model.get('client'));
                    expect(view.$el.find('[name=price]').val()).toEqual(model.get('price'));
                    expect(view.$el.find('[name=course_id]').val()).toEqual(model.get('course_id'));
                    expect(view.$el.find('[name=benefit_type]').val()).toEqual(model.get('benefit_type'));
                    expect(view.$el.find('[name=benefit_value]').val()).toEqual(model.get('benefit_value').toString());
                    expect(view.$el.find('[name=code]').val()).toEqual(model.get('code'));
                    expect(view.$el.find('[name=category]').val()).toEqual(model.get('category').id);
                    expect(view.$el.find('[name=note]').val()).toEqual(model.get('note'));
                });
            });

        });
    }
);

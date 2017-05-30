define([
    'jquery',
    'backbone',
    'js-cookie',
    'moment',
    'underscore',
    'models/coupon_model',
    'test/mock_data/coupons'
],
    function($,
             Backbone,
             Cookies,
             moment,
             _,
             Coupon,
             MockCoupons) {
        'use strict';

        var discountCodeData = MockCoupons.discountCodeCouponModelData,
            enrollmentCodeData = MockCoupons.enrollmentCodeCouponModelData;

        describe('Coupon model', function() {
            describe('url', function() {
                it('should be /api/v2/coupons/ for new instances', function() {
                    var instance = new Coupon();
                    expect(instance.url()).toEqual('/api/v2/coupons/');
                });

                it('should have a trailing slash for existing instances', function() {
                    var id = 1,
                        instance = new Coupon({id: id});
                    expect(instance.url()).toEqual('/api/v2/coupons/' + id + '/');
                });
            });

            describe('validation', function() {
                var model;

                beforeEach(function() {
                    spyOn($, 'ajax');
                    model = Coupon.findOrCreate(discountCodeData, {parse: true});
                });

                it('should validate dates', function() {
                    model.validate();
                    expect(model.isValid()).toBeTruthy();

                    model.set('start_date', 'not a real date');
                    model.set('end_date', 'not a real date');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('start_date', '2015-11-11T00:00:00Z');
                    model.set('end_date', '2015-10-10T00:00:00Z');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate discount code has discount type and value', function() {
                    model.set('benefit_value', '');
                    model.set('benefit_type', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate course ID if the catalog is a Single Course Catalog', function() {
                    model.set('catalog_type', 'Single course');
                    model.set('course_id', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('course_id', 'a/b/c');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate seat type if the catalog is a Single Course Catalog', function() {
                    model.set('catalog_type', 'Single course');
                    model.set('seat_type', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('seat_type', 'Verified');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate catalog query and course seat types for Multiple Courses Catalog', function() {
                    model.set('catalog_type', 'Multiple courses');
                    model.set('catalog_query', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('catalog_query', '*:*');
                    model.set('course_seat_types', []);
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('catalog_query', '');
                    model.set('course_seat_types', ['verified']);
                    model.validate();
                    expect(model.isValid()).toBe(false);

                    model.set('catalog_query', '*:*');
                    model.set('course_seat_types', ['verified']);
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate course catalog and course seat types for type Catalog', function() {
                    model.set('catalog_type', 'Catalog');
                    model.set('course_catalog', '');
                    model.validate();
                    expect(model.isValid()).toBe(false);

                    model.set('course_catalog', '');
                    model.validate();
                    expect(model.isValid()).toBe(false);

                    model.set('course_catalog', '1');
                    model.set('course_seat_types', []);
                    model.validate();
                    expect(model.isValid()).toBe(false);

                    model.set('course_catalog', '1');
                    model.set('course_seat_types', ['verified']);
                    model.validate();
                    expect(model.isValid()).toBe(true);
                });

                it('should validate invoice data.', function() {
                    model.set('price', 'text');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                    model.set('price', 100);
                    model.validate();
                    expect(model.isValid()).toBeTruthy();

                    model.set('invoice_discount_value', 'text');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                    model.set('invoice_discount_value', 100);
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate coupon code.', function() {
                    model.set('code', '!#$%&/()=');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('code', 'CODE12345');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate email domain.', function() {
                    var invalidDomains = [
                            '-invalid.com', 'invalid', 'invalid-.com', 'invalid.c', 'valid.com,',
                            'invalid.photography1', 'valid.com,invalid', 'valid.com,invalid-.com',
                            'valid.com,-invalid.com', 'in--valid.com', 'in..valid.com',
                            'valid.com,invalid.c', 'invalid,valid.com', 'çççç.çç-çç',
                            'ççç.xn--ççççç', 'çççç.çç--çç.ççç'
                        ],
                        validDomains = [
                            'valid.com', 'valid.co', 'valid-domain.com', 'valid.photography',
                            'valid.com,valid.co', 'çççç.рф', 'çç-ççç32.中国', 'ççç.ççç.இலங்கை'
                        ];

                    _.each(invalidDomains, function(domain) {
                        model.set('email_domains', domain);
                        model.validate();
                        expect(model.isValid()).toBeFalsy();
                    });
                    _.each(validDomains, function(domain) {
                        model.set('email_domains', domain);
                        model.validate();
                        expect(model.isValid()).toBeTruthy();
                    });
                });

                it('should validate max_uses value', function() {
                    model.set('max_uses', 'abc');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('max_uses', 1);
                    model.set('voucher_type', 'Multi-use');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('max_uses', 2);
                    model.validate();
                    expect(model.isValid()).toBeTruthy();

                    model.unset('max_uses');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();

                    model.set('max_uses', 1);
                    model.set('voucher_type', 'Once per customer');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });
            });

            describe('test model methods', function() {
                it('should return seat price if a coupon has a seat', function() {
                    var model = new Coupon();

                    expect(model.getSeatPrice()).toEqual('');

                    model.set('seats', [{price: 100}]);
                    expect(model.getSeatPrice()).toEqual(100);
                });
            });

            describe('Should Update Seat Data Correctly.', function() {
                it('should set correct catalog type for each seat.', function() {
                    // Test single course catalog type when a single course is selected for coupon creation.
                    var model = new Coupon({});
                    model.updateSeatData();
                    expect(model.get('catalog_type')).toEqual(model.catalogTypes.single_course);

                    model = new Coupon({
                        course_catalog: 1
                    });
                    model.updateSeatData();
                    expect(model.get('catalog_type')).toEqual(model.catalogTypes.catalog);

                    // Test multiple course type when an catalog query is given for coupon creation.
                    model = new Coupon({
                        catalog_query: '*:*'
                    });
                    model.updateSeatData();
                    expect(model.get('catalog_type')).toEqual(model.catalogTypes.multiple_courses);
                });
            });

            describe('save', function() {
                it('should POST enrollment data', function() {
                    var model, args, ajaxData;
                    spyOn($, 'ajax');
                    model = Coupon.findOrCreate(enrollmentCodeData, {parse: true});
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    args = $.ajax.calls.argsFor(0);
                    ajaxData = JSON.parse(args[0].data);
                    expect(ajaxData.benefit_type).toEqual('Percentage');
                    expect(ajaxData.benefit_value).toEqual(100);
                    expect(ajaxData.quantity).toEqual(1);
                    expect(model.get('start_datetime')).toEqual(moment.utc(model.get('start_date')));
                    expect(model.get('end_datetime')).toEqual(moment.utc(model.get('end_date')));
                });

                it('should POST discount data', function() {
                    var model, args, ajaxData;
                    spyOn($, 'ajax');
                    model = Coupon.findOrCreate(discountCodeData, {parse: true});
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    args = $.ajax.calls.argsFor(0);
                    ajaxData = JSON.parse(args[0].data);
                    expect(ajaxData.quantity).toEqual(1);
                    expect(model.get('start_datetime')).toEqual(moment.utc(model.get('start_date')));
                    expect(model.get('end_datetime')).toEqual(moment.utc(model.get('end_date')));
                });

                it('should format start and end date if they are patch updated', function() {
                    var endDate = '2016-11-11T00:00:00Z',
                        model = Coupon.findOrCreate(discountCodeData, {parse: true}),
                        startDate = '2015-11-11T00:00:00Z',
                        title = 'Coupon title';
                    spyOn(Backbone.RelationalModel.prototype, 'save');
                    model.save(
                        {
                            end_date: endDate,
                            start_date: startDate,
                            title: title
                        },
                        {patch: true}
                    );

                    expect(Backbone.RelationalModel.prototype.save).toHaveBeenCalledWith(
                        {
                            end_date: endDate,
                            end_datetime: moment.utc(endDate),
                            name: title,
                            start_date: startDate,
                            start_datetime: moment.utc(startDate),
                            title: title
                        },
                        {
                            patch: true,
                            headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')},
                            contentType: 'application/json'
                        }
                    );
                });
            });
        });
    });

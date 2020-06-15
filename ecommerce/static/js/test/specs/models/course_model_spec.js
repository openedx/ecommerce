define([
    'jquery',
    'moment',
    'underscore',
    'collections/product_collection',
    'models/course_model',
    'models/course_seats/professional_seat',
    'models/course_seats/audit_seat',
    'models/course_seats/honor_seat',
    'js-cookie'
],
    function($,
              moment,
              _,
              ProductCollection,
              Course,
              ProfessionalSeat,
              AuditSeat,
              HonorSeat,
              Cookies
    ) {
        'use strict';

        var model,
            auditSeat = {
                id: 6,
                url: 'http://ecommerce.local:8002/api/v2/products/6/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with no certificate',
                price: '0.00',
                expires: null,
                attribute_values: [
                    {
                        name: 'course_key',
                        value: 'edX/DemoX/Demo_Course'
                    },
                    {
                        name: 'id_verification_required',
                        value: false
                    }
                ],
                is_available_to_buy: true
            },
            honorSeat = {
                id: 8,
                url: 'http://ecommerce.local:8002/api/v2/products/8/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with honor certificate',
                price: '0.00',
                expires: null,
                attribute_values: [
                    {
                        name: 'certificate_type',
                        value: 'honor'
                    },
                    {
                        name: 'course_key',
                        value: 'edX/DemoX/Demo_Course'
                    },
                    {
                        name: 'id_verification_required',
                        value: false
                    }
                ],
                is_available_to_buy: true
            },
            verifiedSeat = {
                id: 9,
                url: 'http://ecommerce.local:8002/api/v2/products/9/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with verified certificate (and ID verification)',
                price: '15.00',
                expires: '2015-01-01T00:00:00+00:00',
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
            creditSeat = {
                id: 10,
                url: 'http://ecommerce.local:8002/api/v2/products/10/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with credit certificate (and ID verification)',
                price: '200.00',
                expires: null,
                attribute_values: [
                    {
                        name: 'certificate_type',
                        value: 'credit'
                    },
                    {
                        name: 'course_key',
                        value: 'edX/DemoX/Demo_Course'
                    },
                    {
                        name: 'id_verification_required',
                        value: true
                    },
                    {
                        name: 'credit_provider',
                        value: 'Harvard'
                    },
                    {
                        name: 'credit_hours',
                        value: 1
                    }
                ],
                is_available_to_buy: true
            },
            alternateCreditSeat = {
                id: 11,
                url: 'http://ecommerce.local:8002/api/v2/products/11/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with credit certificate (and ID verification)',
                price: '300.00',
                expires: null,
                attribute_values: [
                    {
                        name: 'certificate_type',
                        value: 'credit'
                    },
                    {
                        name: 'course_key',
                        value: 'edX/DemoX/Demo_Course'
                    },
                    {
                        name: 'id_verification_required',
                        value: true
                    },
                    {
                        name: 'credit_provider',
                        value: 'MIT'
                    },
                    {
                        name: 'credit_hours',
                        value: 2
                    }
                ],
                is_available_to_buy: true
            },
            enrollmentCodeProduct = {
                id: 12,
                url: 'http://ecommerce.local:8002/api/v2/products/12/',
                structure: 'standalone',
                product_class: 'Enrollment Code',
                title: 'Enrollent Code for Professional Seat in edX Demonstration Course',
                price: '300.00',
                expires: null,
                attribute_values: [
                    {
                        name: 'seat_type',
                        value: 'professional'
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
                id: 'edX/DemoX/Demo_Course',
                url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/',
                name: 'edX Demonstration Course',
                verification_deadline: '2015-10-01T00:00:00Z',
                honor_mode: false,
                type: 'credit',
                products_url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/products/',
                last_edited: '2015-07-27T00:27:23Z',
                products: [
                    auditSeat,
                    honorSeat,
                    verifiedSeat,
                    creditSeat,
                    alternateCreditSeat,
                    enrollmentCodeProduct,
                    {
                        id: 7,
                        url: 'http://ecommerce.local:8002/api/v2/products/7/',
                        structure: 'parent',
                        product_class: 'Seat',
                        title: 'Seat in edX Demonstration Course',
                        price: null,
                        expires: null,
                        attribute_values: [
                            {
                                name: 'course_key',
                                value: 'edX/DemoX/Demo_Course'
                            }
                        ],
                        is_available_to_buy: false
                    }
                ]
            };

        describe('Course model', function() {
            beforeEach(function() {
                model = Course.findOrCreate(data, {parse: true});

                // Remove the non-essential products
                model.prepareProducts();
            });

            describe('prepareProducts', function() {
                it('should remove all non-essential products from the products collection', function() {
                    var products;

                    // Re-initialize the model since the beforeEach removes the products we don't need
                    model = Course.findOrCreate(data, {parse: true});

                    // Sanity check to ensure the products were properly parsed
                    products = model.get('products');
                    expect(products.length).toEqual(7);

                    // Re-remove the non-essential products
                    model.prepareProducts();

                    // Only the strong survived...
                    expect(products.length).toEqual(5);
                    expect(products.where({structure: 'child'}).length).toEqual(5);
                });
            });

            // NOTE (CCB): There is a bug preventing this from being called 'toJSON'.
            // See https://github.com/karma-runner/karma/issues/1534.
            describe('#toJSON', function() {
                it('should not modify verification_deadline if verification_deadline is empty', function() {
                    var json,
                        values = [null, ''];

                    _.each(values, function(value) {
                        model.set('verification_deadline', value);
                        json = model.toJSON();
                        expect(json.verification_deadline).toEqual(value);
                    });
                });

                it('should add a timezone to verification_deadline if verification_deadline is not empty', function() {
                    var json,
                        deadline = '2015-01-01T00:00:00';

                    model.set('verification_deadline', deadline);
                    json = model.toJSON();

                    expect(json.verification_deadline).toEqual(deadline + '+00:00');
                });
            });

            describe('save', function() {
                var expectedAjaxData = function() {
                    var products,
                        expected = {
                            id: data.id,
                            name: data.name,
                            verification_deadline: moment.utc(data.verification_deadline).format()
                        };

                    products = _.filter(data.products, function(product) {
                        return product.structure === 'child';
                    });

                    expected.products = _.map(products, function(product) {
                        return product;
                    });

                    return expected;
                };

                it('should POST to the publication endpoint', function() {
                    var args,
                        cookie = 'save-test';

                    spyOn($, 'ajax');
                    Cookies.set('ecommerce_csrftoken', cookie);

                    expect(model.validate()).toBeFalsy();
                    model.save();

                    // $.ajax should have been called
                    expect($.ajax).toHaveBeenCalled();

                    // Ensure the data was POSTed to the correct endpoint
                    args = $.ajax.calls.argsFor(0)[0];
                    expect(args.type).toEqual('POST');
                    expect(args.url).toEqual('/api/v2/publication/');
                    expect(args.contentType).toEqual('application/json');
                    expect(args.headers).toEqual({'X-CSRFToken': cookie});
                    expect(JSON.parse(args.data)).toEqual(expectedAjaxData(data));
                });

                describe('when honor_mode true', function() {
                    it('adds an honor seat and removes the audit seat', function() {
                        var seats;

                        model.set('products', []);
                        model.get('products').push(new AuditSeat({}));
                        model.set('honor_mode', true);
                        model.save();

                        seats = model.seats();
                        expect(seats.length).toEqual(1);
                        expect(seats[0].attributes.certificate_type).toEqual('honor');
                    });
                });

                describe('when honor_mode is true and honor seat already exists', function() {
                    it('removes the audit seat and does not add a new honor seat', function() {
                        var seats;

                        model.set('products', []);
                        model.get('products').push(new AuditSeat({}));
                        model.get('products').push(new HonorSeat({}));
                        model.set('honor_mode', true);
                        model.save();

                        seats = model.seats();
                        expect(seats.length).toEqual(1);
                        expect(seats[0].attributes.certificate_type).toEqual('honor');
                    });
                });

                describe('when honor_mode false', function() {
                    it('does not add an honor seat and leaves the audit seat', function() {
                        var seats;

                        model.set('products', []);
                        model.get('products').push(new AuditSeat({}));
                        model.set('honor_mode', false);
                        model.save();

                        seats = model.seats();
                        expect(seats.length).toEqual(1);
                        expect(seats[0].attributes.certificate_type).toBeNull();
                    });
                });
            });

            // FIXME: These tests timeout when run. This is tracked by LEARNER-824.
            xdescribe('getOrCreateSeats', function() {
                it('should return existing seats', function() {
                    var mapping = {
                            audit: [auditSeat],
                            honor: [honorSeat],
                            verified: [verifiedSeat],
                            credit: [creditSeat, alternateCreditSeat]
                        },
                        seats;

                    _.each(mapping, function(expected, seatType) {
                        seats = model.getOrCreateSeats(seatType);
                        _.each(seats, function(seat) {
                            expect(expected).toContain(seat.toJSON());
                        });
                    });
                });

                it('should create a new CourseSeat if one does not exist', function() {
                    var seat;

                    // Sanity check to confirm a new seat is created later
                    expect(model.seats().length).toEqual(5);

                    // A new seat should be created
                    seat = model.getOrCreateSeats('professional')[0];
                    expect(model.seats().length).toEqual(6);

                    // The new seat's class/type should correspond to the passed in seat type
                    expect(seat).toEqual(jasmine.any(ProfessionalSeat));
                });
            });

            // FIXME: This test times out when run. This is tracked by LEARNER-824.
            xdescribe('products', function() {
                it('is a ProductCollection', function() {
                    expect(model.get('products')).toEqual(jasmine.any(ProductCollection));
                });
            });

            describe('verification deadline validation', function() {
                it('succeeds if the verification deadline is after the course seats\' expiration dates', function() {
                    var seat = model.getOrCreateSeats('verified')[0];
                    model.set('products', seat);
                    model.set('verification_deadline', '2016-01-01T00:00:00Z');
                    seat.set('expires', '2015-01-01T00:00:00Z');

                    expect(model.validate()).toBeUndefined();
                    expect(model.isValid(true)).toBeTruthy();
                });

                it('fails if the verification deadline is before the course seats\' expiration dates', function() {
                    var seat = model.getOrCreateSeats('verified')[0],
                        msg = 'The verification deadline must occur AFTER the upgrade deadline.';
                    model.set('verification_deadline', '2014-01-01T00:00:00Z');
                    seat.set('expires', '2015-01-01T00:00:00Z');

                    expect(model.validate().verification_deadline).toEqual(msg);
                    expect(model.isValid(true)).toBeFalsy();
                });
            });

            describe('products validation', function() {
                describe('with single value', function() {
                    it('should return an error message if any product is invalid', function() {
                        var msg = 'Product validation failed.',
                            products = model.get('products');

                        // Add an invalid product
                        products.push(new ProfessionalSeat({price: null}));

                        expect(model.validate().products).toEqual(msg);
                        expect(model.isValid(true)).toBeFalsy();
                    });
                });

                describe('with non-products', function() {
                    it('should have an undefined return value', function() {
                        expect(model.validation.products([])).toBeUndefined();
                    });
                });
            });

            describe('honorModeInit', function() {
                describe('with seats', function() {
                    it('sets honor_mode to true', function() {
                        model.set('honor_mode', null);
                        model.set('products', []);
                        model.get('products').push(new AuditSeat({}));
                        model.get('products').push(new HonorSeat({}));
                        model.honorModeInit();
                        expect(model.get('honor_mode')).toBeTruthy();
                    });

                    it('sets honor_mode to false', function() {
                        model.set('honor_mode', null);
                        model.set('products', []);
                        model.get('products').push(new AuditSeat({}));
                        model.honorModeInit();
                        expect(model.get('honor_mode')).toBeFalsy();
                    });
                });

                describe('without seats', function() {
                    it('should have an undefined return value', function() {
                        model.set('honor_mode', null);
                        model.set('products', []);
                        model.honorModeInit();
                        expect(model.get('honor_mode')).toBeNull();
                    });
                });
            });

            describe('honor mode validation', function() {
                describe('without an honor mode', function() {
                    beforeEach(function() {
                        model = Course.findOrCreate({
                            id: 'test/testX/testcourse',
                            name: 'Test Course',
                            verification_deadline: '2015-10-01T00:00:00Z',
                            honor_mode: null,
                            type: null
                        });
                    });

                    it('is valid for professional education courses', function() {
                        model.set('type', 'professional');
                        expect(model.isValid(true)).toBeTruthy();
                    });

                    it('is not valid for non-prof-ed courses', function() {
                        _.each(['audit', 'verified', 'credit'], function(type) {
                            model.set('type', type);
                            expect(model.isValid(true)).toBeFalsy();
                        });
                    });
                });
            });

            describe('course and course seat name/title validation', function() {
                var validName = 'Random name',
                    invalidName = 'A &amp; test with <a>html</a>';

                it('should succeed if the course name does not contain HTML', function() {
                    model.set('name', validName);
                    expect(model.isValid(true)).toBeTruthy();
                });

                it('should fail if the course name contains HTML', function() {
                    model.set('name', invalidName);
                    expect(model.validate().name).toEqual('The product name cannot contain HTML.');
                    expect(model.isValid(true)).toBeFalsy();
                });

                it('should succeed if the seat title does not contain HTML', function() {
                    model.set('products', [honorSeat]);
                    model.seats()[0].set('title', validName);
                    expect(model.isValid(true)).toBeTruthy();
                });

                it('should fail if the seat title contains HTML', function() {
                    model.set('products', [honorSeat]);
                    model.seats()[0].set('title', invalidName);
                    expect(model.seats()[0].validate().title).toEqual('The product name cannot contain HTML.');
                    expect(model.isValid(true)).toBeFalsy();
                });
            });
        });
    }
);

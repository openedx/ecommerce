define([
        'jquery',
        'moment',
        'underscore',
        'collections/product_collection',
        'models/course_model',
        'models/course_seats/professional_seat',
        'jquery-cookie'
    ],
    function ($,
              moment,
              _,
              ProductCollection,
              Course,
              ProfessionalSeat) {
        'use strict';

        var model,
            honorSeat = {
                id: 9,
                url: 'http://ecommerce.local:8002/api/v2/products/9/',
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
                id: 8,
                url: 'http://ecommerce.local:8002/api/v2/products/8/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with verified certificate (and ID verification)',
                price: '15.00',
                expires: null,
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
                id: 'edX/DemoX/Demo_Course',
                url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/',
                name: 'edX Demonstration Course',
                verification_deadline: '2015-10-01T00:00:00Z',
                type: 'verified',
                products_url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/products/',
                last_edited: '2015-07-27T00:27:23Z',
                products: [
                    honorSeat,
                    verifiedSeat,
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

        beforeEach(function () {
            model = Course.findOrCreate(data, {parse: true});
        });

        describe('removeParentProducts', function () {
            it('should remove all parent products from the products collection', function () {
                var products = model.get('products');

                // Sanity check to ensure the products were properly parsed
                expect(products.length).toEqual(3);

                // Remove the parent products
                model.removeParentProducts();

                // Only the children survived...
                expect(products.length).toEqual(2);
                expect(products.where({structure: 'child'}).length).toEqual(2);
            });
        });

        // NOTE (CCB): There is a bug preventing this from being called 'toJSON'.
        // See https://github.com/karma-runner/karma/issues/1534.
        describe('#toJSON', function () {
            it('should not modify verification_deadline if verification_deadline is empty', function () {
                var json,
                    values = [null, ''];

                _.each(values, function (value) {
                    model.set('verification_deadline', value);
                    json = model.toJSON();
                    expect(json.verification_deadline).toEqual(value);
                });
            });

            it('should add a timezone to verification_deadline if verification_deadline is not empty', function () {
                var json,
                    deadline = '2015-01-01T00:00:00';

                model.set('verification_deadline', deadline);
                json = model.toJSON();

                expect(json.verification_deadline).toEqual(deadline + '+00:00');
            });
        });

        describe('save', function () {
            var expectedAjaxData = function (data) {
                var products,
                    expected = {
                        id: data.id,
                        name: data.name,
                        verification_deadline: moment.utc(data.verification_deadline).format()
                    };

                products = _.filter(data.products, function (product) {
                    return product.structure === 'child';
                });

                expected.products = _.map(products, function (product) {
                    return product;
                });

                return expected;
            };

            it('should POST to the publication endpoint', function () {
                var args,
                    cookie = 'save-test';

                spyOn($, 'ajax');
                $.cookie('ecommerce_csrftoken', cookie);

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
        });

        describe('getOrCreateSeat', function () {
            it('should return existing seats', function () {
                var mapping = {
                    'honor': honorSeat,
                    'verified': verifiedSeat
                };

                _.each(mapping, function (expected, seatType) {
                    expect(model.getOrCreateSeat(seatType).toJSON()).toEqual(expected);
                });
            });

            it('should return null if an audit seat does not already exist', function () {
                expect(model.getOrCreateSeat('audit')).toBeUndefined();
            });

            it('should create a new CourseSeat if one does not exist', function () {
                var seat;

                // Sanity check to confirm a new seat is created later
                expect(model.seats().length).toEqual(2);

                // A new seat should be created
                seat = model.getOrCreateSeat('professional');
                expect(model.seats().length).toEqual(3);

                // The new seat's class/type should correspond to the passed in seat type
                expect(seat).toEqual(jasmine.any(ProfessionalSeat));
            });
        });

        describe('products', function () {
            it('is a ProductCollection', function () {
                expect(model.get('products')).toEqual(jasmine.any(ProductCollection));
            });
        });
    }
);

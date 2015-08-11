define([
        'underscore',
        'models/course_model'
    ],
    function (_,
              Course) {
        'use strict';

        var model,
            data = {
                id: 'edX/DemoX/Demo_Course',
                url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/',
                name: 'edX Demonstration Course',
                verification_deadline: null,
                type: 'verified',
                products_url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/products/',
                last_edited: '2015-07-27T00:27:23Z',
                products: [
                    {
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
                    {
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
    }
);

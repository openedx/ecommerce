define([
        'underscore',
        'models/product_model'
    ],
    function (_,
              Product) {
        'use strict';

        var model,
            data = {
                id: 8,
                url: 'http://ecommerce.local:8002/api/v2/products/8/',
                structure: 'child',
                product_class: 'Seat',
                title: 'Seat in edX Demonstration Course with verified certificate (and ID verification)',
                price: '15.00',
                expires: '2016-01-01T00:00:00Z',
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
            };

        beforeEach(function () {
            model = Product.findOrCreate(data, {parse: true});
        });

        describe('Product model', function () {
            // NOTE (CCB): There is a bug preventing this from being called 'toJSON'.
            // See https://github.com/karma-runner/karma/issues/1534.
            describe('#toJSON', function () {
                it('should not modify expires if expires is empty', function () {
                    var json,
                        values = [null, ''];

                    _.each(values, function (value) {
                        model.set('expires', value);
                        json = model.toJSON();
                        expect(json.expires).toEqual(value);
                    });
                });

                it('should add a timezone to expires if expires is not empty', function () {
                    var json,
                        deadline = '2015-01-01T00:00:00';

                    model.set('expires', deadline);
                    json = model.toJSON();

                    expect(json.expires).toEqual(deadline + '+00:00');
                });

                it('should re-nest the un-nested attributes', function () {
                    var json = model.toJSON();

                    // Sanity check
                    expect(model.get('certificate_type')).toEqual('verified');
                    expect(model.get('course_key')).toEqual('edX/DemoX/Demo_Course');
                    expect(model.get('id_verification_required')).toEqual(true);

                    // Very the attributes have been re-nested
                    expect(json.attribute_values).toEqual(data.attribute_values);
                });
            });
        });
    }
);

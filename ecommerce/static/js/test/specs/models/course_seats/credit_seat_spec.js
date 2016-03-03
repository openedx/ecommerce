define([

        'collections/credit_provider_collection',
        'ecommerce',
        'models/course_seats/credit_seat'
    ],
    function (CreditProviderCollection,
              ecommerce,
              CreditSeat) {
        'use strict';

        var model,
            data = {
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
                        value: 'credit'
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
            };

        beforeEach(function () {
            model = CreditSeat.findOrCreate(data, {parse: true});
            ecommerce.credit.providers = new CreditProviderCollection([{id: 'harvard', display_name: 'Harvard'}]);
        });

        describe('Credit course seat model', function () {

            describe('credit provider validation', function () {
                function assertCreditProviderInvalid(credit_provider, expected_msg) {
                    model.set('credit_provider', credit_provider);
                    expect(model.validate().credit_provider).toEqual(expected_msg);
                    expect(model.isValid(true)).toBeFalsy();
                }

                it('should do nothing if the credit provider is valid', function () {
                    model.set('credit_provider', ecommerce.credit.providers.at(0).get('id'));
                    expect(model.validate().credit_provider).toBeUndefined();
                });

                it('should return a message if the credit provider is not set', function () {
                    var msg = 'All credit seats must have a credit provider.',
                        values = [null, undefined, ''];

                    values.forEach(function (value) {
                        assertCreditProviderInvalid(value, msg);
                    });
                });

                it('should return a message if the credit provider is not a valid credit provider', function () {
                    var msg = 'Please select a valid credit provider.';
                    assertCreditProviderInvalid('acme', msg);
                });
            });
        });
    }
);

define([
        'underscore',
        'models/course_seats/course_seat'
    ],
    function (_,
              CourseSeat) {
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
            };

        beforeEach(function () {
            model = CourseSeat.findOrCreate(data, {parse: true});
        });

        describe('getSeatType', function () {
            it('should return a seat type corresponding to the certificate type', function () {
                var mappings = {
                    'credit': 'credit',
                    'honor': 'honor',
                    'no-id-professional': 'professional',
                    'professional': 'professional',
                    'verified': 'verified'
                };

                _.each(mappings, function (seatType, certificateType) {
                    model.set('certificate_type', certificateType);
                    expect(model.getSeatType()).toEqual(seatType);
                });
            });

            it('should return audit for empty certificate types', function () {
                var certificate_types = ['', null];

                _.each(certificate_types, function (certificateType) {
                    model.set('certificate_type', certificateType);
                    expect(model.getSeatType()).toEqual('audit');
                });
            });
        });

        describe('getSeatTypeDisplayName', function () {
            it('should return a value corresponding to the certificate type', function () {
                var mappings = {
                    'credit': 'Credit',
                    'honor': 'Honor',
                    'no-id-professional': 'Professional',
                    'professional': 'Professional',
                    'verified': 'Verified'
                };

                _.each(mappings, function (seatType, certificateType) {
                    model.set('certificate_type', certificateType);
                    expect(model.getSeatTypeDisplayName()).toEqual(seatType);
                });
            });

            it('should return Audit for empty certificate types', function () {
                var certificate_types = ['', null];

                _.each(certificate_types, function (certificateType) {
                    model.set('certificate_type', certificateType);
                    expect(model.getSeatTypeDisplayName()).toEqual('Audit');
                });
            });
        });

        describe('getCertificateDisplayName', function () {
            it('should return a value corresponding to the certificate type', function () {
                var mappings = {
                    'credit': 'Verified Certificate',
                    'honor': 'Honor Certificate',
                    'no-id-professional': 'Professional Certificate',
                    'professional': 'Professional Certificate',
                    'verified': 'Verified Certificate'
                };

                _.each(mappings, function (seatType, certificateType) {
                    model.set('certificate_type', certificateType);
                    expect(model.getCertificateDisplayName()).toEqual(seatType);
                });
            });

            it('should return (No Certificate) for empty certificate types', function () {
                var certificate_types = ['', null];

                _.each(certificate_types, function (certificateType) {
                    model.set('certificate_type', certificateType);
                    expect(model.getCertificateDisplayName()).toEqual('(No Certificate)');
                });
            });
        });
    }
);

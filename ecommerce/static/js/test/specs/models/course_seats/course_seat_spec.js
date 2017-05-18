define([
        'underscore',
        'models/course_model',
        'models/course_seats/course_seat'
    ],
    function (_,
              Course,
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

        describe('Course seat model', function () {
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

            describe('expires validation', function () {
                function assertExpiresInvalid(expires, verification_deadline) {
                    var msg = 'The upgrade deadline must occur BEFORE the verification deadline.';
                    model.set('expires', expires);
                    model.course = Course.findOrCreate({id: 'a/b/c', verification_deadline: verification_deadline});
                    expect(model.validate().expires).toEqual(msg);
                    expect(model.isValid(true)).toBeFalsy();
                }

                it('should do nothing if the CourseSeat has no associated Course', function () {
                    model.course = null;
                    expect(model.validation.expires('2015-01-01')).toBeUndefined();
                });

                it('should do nothing if the CourseSeat has no expiration value set', function () {
                    expect(model.validation.expires(null)).toBeUndefined();
                    expect(model.validation.expires(undefined)).toBeUndefined();
                });

                it('should return a message if the CourseSeat expires after the Course verification deadline',
                    function () {
                        assertExpiresInvalid('2016-01-01', '2014-01-01');
                    }
                );

                it('should return a message if the CourseSeat expires at the same time verification closes',
                    function () {
                        assertExpiresInvalid('2016-01-01', '2016-01-01');
                    }
                );
            });
        });
    }
);

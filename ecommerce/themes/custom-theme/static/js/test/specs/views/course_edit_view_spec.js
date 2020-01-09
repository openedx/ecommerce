define([
    'jquery',
    'underscore',
    'underscore.string',
    'moment',
    'views/course_create_edit_view',
    'models/course_model',
    'utils/utils',
    'collections/credit_provider_collection',
    'ecommerce'
],
    function($,
             _,
             _s,
             moment,
             CourseCreateEditView,
             Course,
             Utils,
             CreditProviderCollection,
             ecommerce) {
        'use strict';

        describe('course edit view', function() {
            var view,
                model,
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
                creditSeat = {
                    id: 10,
                    url: 'http://ecommerce.local:8002/api/v2/products/10/',
                    structure: 'child',
                    product_class: 'Seat',
                    title: 'Seat in edX Demonstration Course with credit certificate (and ID verification)',
                    price: '200.00',
                    expires: '2020-01-01T00:00:00Z',
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
                            value: 'harvard'
                        },
                        {
                            name: 'credit_hours',
                            value: 1
                        }
                    ],
                    is_available_to_buy: true
                },
                professionalSeat = {
                    id: 11,
                    url: 'http://ecommerce.local:8002/api/v2/products/8/',
                    structure: 'child',
                    product_class: 'Seat',
                    title: 'Seat in edX Demonstration Course with professional certificate',
                    price: '100.00',
                    expires: null,
                    attribute_values: [
                        {
                            name: 'certificate_type',
                            value: 'professional'
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
                data = {
                    id: 'edX/DemoX/Demo_Course',
                    url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/',
                    name: 'edX Demonstration Course',
                    verification_deadline: null,
                    honor_mode: false,
                    type: 'credit',
                    products_url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/products/',
                    last_edited: '2015-07-27T00:27:23Z',
                    products: [
                        auditSeat,
                        verifiedSeat,
                        creditSeat,
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

            beforeEach(function() {
                ecommerce.credit.providers = new CreditProviderCollection([{id: 'harvard', display_name: 'Harvard'}]);
                model = Course.findOrCreate(data, {parse: true});
                view = new CourseCreateEditView({model: model, editing: true}).render();
            });

            it('should display course details in form fields', function() {
                var checkedRadios = view.$el.find('.course-types input[type=radio]:checked'),
                    typeLabel = checkedRadios.siblings('.course-type-display-name');

                expect(view.$el.find('[name=id]').val()).toEqual(model.get('id'));
                expect(view.$el.find('[name=name]').val()).toEqual(model.get('name'));
                expect(typeLabel.text()).toEqual(_s.capitalize(model.get('type')));
            });

            it('should display correct course seats given course type', function() {
                var $auditElement = view.$el.find('.row.course-seat.audit'),
                    $verifiedElement = view.$el.find('.row.course-seat.verified'),
                    $creditElement = view.$el.find('.row.credit'),
                    $creditSeats = $creditElement.find('.course-seat'),
                    $professionalElement,
                    seat;

                expect($auditElement.length).toBe(1);
                expect($auditElement.find('.seat-price').text()).toBe('$0.00');

                expect($verifiedElement.length).toBe(1);
                expect($verifiedElement.find('[name=price]').val()).toBe('15.00');
                expect($verifiedElement.find('[name=expires]').val()).toBe(Utils.stripTimezone('2020-01-01T00:00:00Z'));

                expect($creditElement.length).toBe(1);
                seat = _.last($creditSeats);
                expect($(seat).find('[name=credit_provider]').val()).toBe('harvard');
                expect($(seat).find('[name=price]').val()).toBe('200.00');
                expect($(seat).find('[name=credit_hours]').val()).toBe('1');
                expect($(seat).find('[name=expires]').val()).toBe(Utils.stripTimezone('2020-01-01T00:00:00Z'));

                // Remove audit, verified, and credit seats, and add a professional seat
                data.products.splice(0, 3, professionalSeat);
                data.type = 'professional';

                model = Course.findOrCreate(data, {parse: true, merge: true});
                view = new CourseCreateEditView({model: model, editing: true}).render();

                $professionalElement = view.$el.find('.row.course-seat.professional');
                expect($professionalElement.length).toBe(1);
                expect($professionalElement.find('[name=price]').val()).toBe('100.00');
                expect($professionalElement.find('[name=expires]').val()).toBe('');
            });

            it('should remove the edit form if the view is removed', function() {
                view.remove();
                expect(view.$el.find('.course-form-view').length).toEqual(0);
            });
        });
    }
);

define([
        'underscore.string',
        'moment',
        'views/course_create_edit_view',
        'views/course_seat_form_fields/honor_course_seat_form_field_view',
        'views/course_seat_form_fields/verified_course_seat_form_field_view',
        'models/course_model',
        'utils/utils',
    ],
    function (_s,
              moment,
              CourseCreateEditView,
              HonorCourseSeatFormFieldView,
              VerifiedCourseSeatFormFieldView,
              Course,
              Utils) {

        'use strict';

        describe('course edit view', function () {
            var view,
                model,
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
                view = new CourseCreateEditView({ model: model, editing: true }).render();
            });

            it('should display course details in form fields', function () {
                var checked_radios = view.$el.find('.course-types input[type=radio]:checked'),
                    type_label = checked_radios.siblings('.course-type-display-name');

                expect(view.$el.find('[name=id]').val()).toEqual(model.get('id'));
                expect(view.$el.find('[name=name]').val()).toEqual(model.get('name'));
                expect(type_label.text()).toEqual(_s.capitalize(model.get('type')));
            });

            it('should display correct course seats given course type', function () {
                var honorElement = view.$el.find('.row.course-seat.honor'),
                    verifiedElement = view.$el.find('.row.course-seat.verified');

                expect(honorElement.length).toBe(1);
                expect(honorElement.find('.seat-price').text()).toBe('$0.00');

                expect(verifiedElement.length).toBe(1);
                expect(verifiedElement.find('[name=price]').val()).toBe('15.00');
                expect(verifiedElement.find('[name=expires]').val()).toBe(Utils.stripTimezone('2020-01-01T00:00:00Z'));
            });

            it('should remove the edit form if the view is removed', function () {
                view.remove();
                expect(view.$el.find('.course-form-view').length).toEqual(0);
            });
        });
    }
);

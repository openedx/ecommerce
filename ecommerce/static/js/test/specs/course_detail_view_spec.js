define([
        'jquery',
        'underscore.string',
        'models/course_model',
        'views/course_detail_view'
    ],
    function ($, _s, CourseModel, CourseDetailView) {
        describe('course detail view', function () {
            var $el,
                model,
                server,
                CONTENT_JSON = { 'Content-Type': 'application/json'},
                course_id_pattern = '([^/\+]\+(/|\\+)[^/\+]\+(/|\\+)[^/]\+)',
                course_id = 'edX/DemoX/Demo_Course',
                course_name = 'edX Demonstration Course',
                course_type = 'verified',
                view = {};

            beforeEach(function () {
                //$el = $('<div class="course-detail-view" data-course-id="' + course_id + '"></div>');
                $(document.body).append($el);

                // Mock the API server
                server = sinon.fakeServer.create();
                server.respondImmediately = true;

                // Mock the course detail endpoint
                server.respondWith('GET', new RegExp('\/api\/v2\/courses\/(' + encodeURIComponent(course_id) + ')'),
                    function (xhr, id) {
                        id = decodeURIComponent(id);
                        xhr.respond(
                            200,
                            CONTENT_JSON,
                            JSON.stringify({
                                id: id,
                                name: course_name,
                                type: course_type,
                                products_url: 'http://localhost:9876/api/v2/courses/' + id + '/products',
                                last_edited: '2015-07-01T00:00:00Z'
                            })
                        );
                    }
                );

                // Mock the course product list endpoint
                server.respondWith('GET', new RegExp('\/api\/v2\/courses\/' + course_id + '\/products'),
                    function (xhr, id) {
                        id = decodeURIComponent(id);
                        xhr.respond(
                            200,
                            CONTENT_JSON,
                            JSON.stringify({
                                count: 3,
                                next: null,
                                previous: null,
                                results: [
                                    {
                                        id: 1,
                                        url: 'http://localhost:9876/api/v2/products/1/',
                                        structure: 'child',
                                        product_class: 'Seat',
                                        title: 'Seat in ' + course_name,
                                        price: null,
                                        expires: null,
                                        attribute_values: [
                                            {
                                                name: 'course_key',
                                                value: id
                                            }
                                        ],
                                        is_available_to_buy: false
                                    },
                                    {
                                        id: 2,
                                        url: 'http://localhost:9876/api/v2/products/2/',
                                        structure: 'child',
                                        product_class: 'Seat',
                                        title: 'Seat in ' + course_name + ' with honor certificate',
                                        price: '0.00',
                                        expires: null,
                                        attribute_values: [
                                            {
                                                name: 'certificate_type',
                                                value: 'honor'
                                            },
                                            {
                                                name: 'course_key',
                                                value: id
                                            },
                                            {
                                                name: 'id_verification_required',
                                                value: false
                                            }
                                        ],
                                        is_available_to_buy: true
                                    },
                                    {
                                        id: 3,
                                        url: 'http://localhost:9876/api/v2/products/3/',
                                        structure: 'child',
                                        product_class: 'Seat',
                                        title: 'Seat in ' + course_name + ' with verified certificate (and ID verification)',
                                        price: '50.00',
                                        expires: null,
                                        attribute_values: [
                                            {
                                                name: 'certificate_type',
                                                value: 'verified'
                                            },
                                            {
                                                name: 'course_key',
                                                value: id
                                            },
                                            {
                                                name: 'id_verification_required',
                                                value: false
                                            }
                                        ],
                                        is_available_to_buy: true
                                    }
                                ]
                            })
                        );
                    }
                );

                model = new CourseModel({id: course_id, name: course_name, type: course_type});
                view = new CourseDetailView({model: model});
            });

            afterEach(function () {
                server.restore();
            });

            it('should list basic course info', function () {

                view.render();

                expect(document.title).toEqual(course_name + ' - View Course');
                expect(view.$el.find('.course-name').text()).toEqual(course_name);
                expect(view.$el.find('.course-type').text()).toEqual(_s.capitalize(course_type))
            });

            it('should display the correct number of seats', function () {

                view.renderSeats();

                expect(view.$el.find('.course-seat').length).toEqual(3);
            });
        });
    }
);

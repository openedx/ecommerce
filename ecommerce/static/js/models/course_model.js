// jscs:disable requireCapitalizedConstructors

define([
        'backbone',
        'backbone.relational',
        'backbone.super',
        'backbone.validation',
        'jquery',
        'jquery-cookie',
        'moment',
        'underscore',
        'collections/product_collection',
        'models/course_seats/course_seat',
        'utils/course_utils',
        'utils/utils'
    ],
    function (Backbone,
              BackboneRelational,
              BackboneSuper,
              BackboneValidation,
              $,
              $cookie,
              moment,
              _,
              ProductCollection,
              CourseSeat,
              CourseUtils,
              Utils) {
        'use strict';

        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        _.extend(Backbone.Validation.patterns, {
            courseId: /[^/+]+(\/|\+)[^/+]+(\/|\+)[^/]+/
        });

        _.extend(Backbone.Validation.messages, {
            courseId: gettext('The course ID is invalid.')
        });

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/courses/',

            defaults: {
                id: null,
                name: null,
                type: null,
                verification_deadline: null
            },

            validation: {
                id: {
                    required: true,
                    pattern: 'courseId'
                },
                name: {
                    required: true
                },
                type: {
                    required: true,
                    msg: gettext('You must select a course type.')
                },
                verification_deadline: function (value) {
                    var invalid;

                    // No validation is needed for empty values
                    if (_.isEmpty(value)) {
                        return;
                    }

                    // Find seats where the verification deadline occurs before the upgrade deadline.
                    invalid = _.some(this.seats(), function (seat) {
                        var expires = seat.get('expires');
                        return expires && moment(value).isBefore(expires);
                    });

                    if (invalid) {
                        return gettext('The verification deadline must occur AFTER the upgrade deadline.');
                    }
                },
                products: function (value) {
                    // NOTE (CCB): When syncing from the server, the value is an array. We can safely ignore
                    // validation in this case since the values from the server should be valid.
                    if (!_.isArray(value) && !value.isValid()) {
                        return gettext('Product validation failed.');
                    }
                }
            },

            labels: {
                id: gettext('Course ID'),
                name: gettext('Course Name'),
                type: gettext('Course Type'),
                verification_deadline: gettext('Verification Deadline')
            },

            relations: [{
                collectionType: ProductCollection,
                type: Backbone.HasMany,
                key: 'products',
                relatedModel: CourseSeat,
                includeInJSON: false,
                parse: true,
                collectionOptions: function (model) {
                    return {course: model};
                }
            }],

            /**
             * Mapping of course type to an array of course seat types.
             */
            courseTypeSeatMapping: {
                honor: ['audit', 'honor'],
                verified: ['audit', 'honor', 'verified'],
                professional: ['professional'],
                credit: ['audit', 'honor', 'verified', 'credit']
            },

            /**
             * Seat types that can be created by the user.
             *
             * Note that audit seats cannot be created, only edited.
             */
            creatableSeatTypes: ['honor', 'verified', 'professional', 'credit'],

            initialize: function () {
                this.get('products').on('change:id_verification_required', this.triggerIdVerified, this);
                this.on('sync', this.removeParentProducts, this);
            },

            parse: function (response) {
                response = this._super(response);

                // Form fields display date-times in the user's local timezone. We want all
                // times to be displayed in UTC to avoid confusion. Strip the timezone data to workaround the UI
                // deficiencies. We will restore the UTC timezone in toJSON().
                response.verification_deadline = Utils.stripTimezone(response.verification_deadline);

                return response;
            },

            toJSON: function () {
                var data = this._super();

                // Restore the timezone component, and output the ISO 8601 format expected by the server.
                data.verification_deadline = Utils.restoreTimezone(data.verification_deadline);

                return data;
            },

            /**
             * Alerts listeners that this Course's ID verification status MAY have changed.
             */
            triggerIdVerified: function () {
                this.trigger('change:id_verification_required', this.isIdVerified());
            },

            /**
             * Removes the parent products from the Product collection.
             *
             * This product is never exposed to the user, and should be ignored for all data operations.
             */
            removeParentProducts: function () {
                var products = this.get('products'),
                    parents = products.where({structure: 'parent'});

                products.remove(parents);
            },

            /**
             * Returns all seats related to this course
             *
             * @returns {CourseSeat[]}
             */
            seats: function () {
                return this.get('products').filter(function (product) {
                    // Filter out parent products since there is no need to display or modify.
                    return (product instanceof CourseSeat) && product.get('structure') !== 'parent';
                });
            },

            /**
             * Returns existing CourseSeats corresponding to the given seat type. If none
             * are not found, creates a new one.
             *
             * @param {String} seatType
             * @returns {CourseSeat[]}
             */
            getOrCreateSeats: function (seatType) {
                var seatClass,
                    seats = _.filter(this.seats(), function (product) {
                        // Find the seats with the specific seat type
                        return product.getSeatType() === seatType;
                    }),
                    seat;

                if (_.isEmpty(seats) && _.contains(this.creatableSeatTypes, seatType)) {
                    seatClass = CourseUtils.getCourseSeatModel(seatType);
                    /*jshint newcap: false */
                    seat = new seatClass({course: this});
                    /*jshint newcap: true */
                    this.get('products').add(seat);
                    seats.push(seat);
                }

                return seats;
            },

            /**
             * Returns boolean indicating if this Course is verified.
             *
             * A Course is considered verified if any of its seats requires ID verification.
             *
             * @returns {boolean}
             */
            isIdVerified: function () {
                return Boolean(_.find(this.getCleanProducts(), function (seat) {
                    return seat.get('id_verification_required');
                }, this));
            },

            /**
             * Returns an array of seat types relevant to this Course, based on its type.
             *
             * @returns {String[]} - Array of course seat types, or an empty array if the course type is unrecognized.
             */
            validSeatTypes: function () {
                return _.result(this.courseTypeSeatMapping, this.get('type'), []);
            },

            /**
             * Returns an array of Products relevant to this Course, based on its course type.
             *
             * This method is primarily intended to clean Products models created to support
             * the course form view.
             *
             * @returns {Product[]}
             */
            getCleanProducts: function () {
                return this.seats().filter(function (seat) {
                    return _.contains(this.validSeatTypes(), seat.getSeatType());
                }, this);
            },

            /**
             * Save the Course using the publication endpoint.
             *
             * We use this endpoint because it saves the data, and publishes it
             * to external systems, in an atomic fashion. This is desirable to
             * avoid synchronization issues across systems.
             */
            save: function (options) {
                var verificationDeadline,
                    data = {
                        id: this.get('id'),
                        name: this.get('name'),
                        verification_deadline: null
                    };

                // Submit only the relevant products
                data.products = _.map(this.getCleanProducts(), function (product) {
                    return product.toJSON();
                }, this);

                if (this.isIdVerified()) {
                    verificationDeadline = this.get('verification_deadline');

                    if (verificationDeadline) {
                        data.verification_deadline = moment.utc(verificationDeadline).format();
                    }
                }

                _.defaults(options || (options = {}), {
                    // Always use POST to avoid having to create a parameterized URL
                    type: 'POST',

                    // Use the publication endpoint
                    url: '/api/v2/publication/',

                    // The API requires a CSRF token for all POST requests using session authentication.
                    headers: {'X-CSRFToken': $.cookie('ecommerce_csrftoken')},

                    // JSON or bust!
                    contentType: 'application/json'
                });

                // Override the data and URL to use the publication endpoint.
                options.data = JSON.stringify(data);

                return this._super(null, options);
            }
        });
    }
);

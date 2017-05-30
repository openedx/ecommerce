// jscs:disable requireCapitalizedConstructors

define([
    'backbone',
    'backbone.relational',
    'backbone.super',
    'backbone.validation',
    'jquery',
    'js-cookie',
    'moment',
    'underscore',
    'collections/product_collection',
    'models/course_seats/course_seat',
    'utils/course_utils',
    'utils/utils',
    'utils/validation_patterns'
],
    function(Backbone,
              BackboneRelational,
              BackboneSuper,
              BackboneValidation,
              $,
              Cookies,
              moment,
              _,
              ProductCollection,
              CourseSeat,
              CourseUtils,
              Utils) {
        'use strict';

        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/courses/',

            defaults: {
                id: null,
                name: null,
                type: null,
                verification_deadline: null,
                honor_mode: null
            },

            validation: {
                id: {
                    required: true,
                    pattern: 'courseId'
                },
                name: {
                    required: true,
                    pattern: 'productName'
                },
                type: {
                    required: true,
                    msg: gettext('You must select a course type.')
                },
                honor_mode: {
                    required: function() {
                        return this.includeHonorMode();
                    },
                    msg: gettext('You must choose if an honor seat should be created.')
                },
                verification_deadline: function(value) {
                    var invalid;

                    // No validation is needed for empty values
                    if (_.isEmpty(value)) {
                        return undefined;
                    }

                    // Find seats where the verification deadline occurs before the upgrade deadline.
                    invalid = _.some(this.seats(), function(seat) {
                        var expires = seat.get('expires');
                        return expires && moment(value).isBefore(expires);
                    });

                    if (invalid) {
                        return gettext('The verification deadline must occur AFTER the upgrade deadline.');
                    }

                    return undefined;
                },
                products: function(value) {
                    // NOTE (CCB): When syncing from the server, the value is an array. We can safely ignore
                    // validation in this case since the values from the server should be valid.
                    if (!_.isArray(value) && !value.isValid()) {
                        return gettext('Product validation failed.');
                    }

                    return undefined;
                }
            },

            labels: {
                id: gettext('Course ID'),
                name: gettext('Course Name'),
                type: gettext('Course Type'),
                verification_deadline: gettext('Verification Deadline'),
                honor_mode: gettext('Include Honor Seat')
            },

            relations: [{
                collectionType: ProductCollection,
                type: Backbone.HasMany,
                key: 'products',
                relatedModel: CourseSeat,
                includeInJSON: false,
                parse: true,
                collectionOptions: function(model) {
                    return {course: model};
                }
            }],

            /**
             * Mapping of course type to an array of valid course seat types.
             */
            validCourseTypeSeatMapping: {
                audit: ['audit', 'honor'],
                verified: ['audit', 'verified', 'honor'],
                professional: ['professional'],
                credit: ['audit', 'verified', 'credit', 'honor']
            },

            /**
             * Mapping of course type to an array of active course seat types.
             */
            activeCourseTypeSeatMapping: {
                audit: ['audit'],
                verified: ['audit', 'verified'],
                professional: ['professional'],
                credit: ['audit', 'verified', 'credit']
            },

            /**
             * Seat types that can be created by the user.
             */
            creatableSeatTypes: ['audit', 'honor', 'verified', 'professional', 'credit'],

            initialize: function() {
                this.get('products').on('change:id_verification_required', this.triggerIdVerified, this);
                this.on('sync', this.prepareProducts, this);
                this.on('sync', this.honorModeInit, this);
            },

            parse: function(response) {
                var responseReassigned = this._super(response);

                // Form fields display date-times in the user's local timezone. We want all
                // times to be displayed in UTC to avoid confusion. Strip the timezone data to workaround the UI
                // deficiencies. We will restore the UTC timezone in toJSON().
                // eslint-disable-next-line
                responseReassigned.verification_deadline = Utils.stripTimezone(responseReassigned.verification_deadline);

                return responseReassigned;
            },

            toJSON: function() {
                var data = this._super();

                // Restore the timezone component, and output the ISO 8601 format expected by the server.
                data.verification_deadline = Utils.restoreTimezone(data.verification_deadline);

                return data;
            },

            /**
             * Alerts listeners that this Course's ID verification status MAY have changed.
             */
            triggerIdVerified: function() {
                this.trigger('change:id_verification_required', this.isIdVerified());
            },

            /**
             * Return boolean if this Course has seats and one of them is Honor.
             */
            honorModeInit: function() {
                var honorSeat;

                if (this.seats().length > 0) {
                    honorSeat = _.find(
                        this.seats(),
                        function(seat) {
                            return seat.attributes.certificate_type === 'honor';
                        }
                    );

                    this.set('honor_mode', !!honorSeat);
                }
            },

            /**
             * Returns the subset of pertinent child seat products from the Product collection.
             */
            prepareProducts: function() {
                var products, parents, seats;

                // Create a reference to the current product collection
                products = this.get('products');

                // Ignore any parent product models
                parents = products.where({structure: 'parent'});
                products.remove(parents);

                // Ignore any non-Seat models (such as an Enrollment Code)
                seats = products.where({product_class: 'Seat'});
                products.reset(seats);
            },

            /**
             * Returns all seats related to this course
             *
             * @returns {CourseSeat[]}
             */
            seats: function() {
                return this.get('products').filter(function(product) {
                    // Filter out parent products since there is no need to display or modify.
                    return (product instanceof CourseSeat) &&
                        product.get('structure') !== 'parent' &&
                        product.get('product_class') === 'Seat';
                });
            },

            /**
             * Returns existing CourseSeats corresponding to the given seat type. If none
             * are not found, creates a new one.
             *
             * @param {String} seatType
             * @returns {CourseSeat[]}
             */
            getOrCreateSeats: function(seatType) {
                var seatClass,
                    seats = _.filter(this.seats(), function(product) {
                        // Find the seats with the specific seat type
                        return product.getSeatType() === seatType;
                    }),
                    seat;

                if (_.isEmpty(seats) && _.contains(this.creatableSeatTypes, seatType)) {
                    seatClass = CourseUtils.getCourseSeatModel(seatType);
                    /* jshint newcap: false */
                    seat = new seatClass({course: this});
                    /* jshint newcap: true */
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
            isIdVerified: function() {
                return Boolean(_.find(this.getCleanProducts(), function(seat) {
                    return seat.get('id_verification_required');
                }, this));
            },

            /**
             * Returns boolean indicating if this Course should include an honor seat.
             *
             * @returns {boolean}
             */
            includeHonorMode: function() {
                return this.get('type') && this.get('type') !== 'professional';
            },

            /**
             * Returns an array of valid seat types relevant to this Course, based on its type.
             *
             * @returns {String[]} - Array of course seat types, or an empty array if the course type is unrecognized.
             */
            validSeatTypes: function() {
                return _.result(this.validCourseTypeSeatMapping, this.get('type'), []);
            },

            /**
             * Returns an array of active seat types relevant to this Course, based on its type.
             *
             * @returns {String[]} - Array of course seat types, or an empty array if the course type is unrecognized.
             */
            activeSeatTypes: function() {
                return _.result(this.activeCourseTypeSeatMapping, this.get('type'), []);
            },

            /**
             * Returns an array of Products relevant to this Course, based on its course type.
             *
             * This method is primarily intended to clean Products models created to support
             * the course form view.
             *
             * @returns {Product[]}
             */
            getCleanProducts: function() {
                return this.seats().filter(function(seat) {
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
            save: function(attributes, options) {
                var verificationDeadline,
                    honorMode,
                    honorSeatClass,
                    honorSeat,
                    products,
                    auditSeat,
                    data = {
                        id: this.get('id'),
                        name: this.get('name'),
                        verification_deadline: null,
                        create_or_activate_enrollment_code: this.get('has_active_bulk_enrollment_code') || false
                    };

                if (this.includeHonorMode()) {
                    honorMode = this.get('honor_mode');

                    if (honorMode) {
                        honorSeatClass = CourseUtils.getCourseSeatModel('honor');
                        /* jshint newcap: false */
                        honorSeat = new honorSeatClass({course: this});
                        /* jshint newcap: true */

                        products = this.get('products');
                        auditSeat = products.where({certificate_type: null});

                        products.remove(auditSeat);
                        products.add(honorSeat);
                    }
                }

                // Submit only the relevant products
                data.products = _.map(this.getCleanProducts(), function(product) {
                    return product.toJSON();
                }, this);

                if (this.isIdVerified()) {
                    verificationDeadline = this.get('verification_deadline');

                    if (verificationDeadline) {
                        data.verification_deadline = moment.utc(verificationDeadline).format();
                    }
                }

                // eslint-disable-next-line no-param-reassign
                _.defaults(options || (options = {}), {
                    // Always use POST to avoid having to create a parameterized URL
                    type: 'POST',

                    // Use the publication endpoint
                    url: '/api/v2/publication/',

                    // The API requires a CSRF token for all POST requests using session authentication.
                    headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')},

                    // JSON or bust!
                    contentType: 'application/json'
                });

                // Override the data and URL to use the publication endpoint.
                // eslint-disable-next-line no-param-reassign
                options.data = JSON.stringify(data);

                return this._super(null, options);
            }
        });
    }
);

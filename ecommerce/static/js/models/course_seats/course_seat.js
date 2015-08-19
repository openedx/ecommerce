define([
        'moment',
        'models/product_model'
    ],
    function (moment,
              Product) {
        'use strict';

        return Product.extend({
            defaults: {
                certificate_type: null,
                expires: null,
                id_verification_required: null,
                price: 0,
                credit_provider: null,
                credit_hours: null,
                product_class: 'Seat'
            },

            course: null,

            validation: {
                price: {
                    required: true,
                    pattern: 'number',
                    msg: gettext('All course seats must have a price.')
                },
                product_class: {
                    oneOf: ['Seat']
                },
                expires: function (value) {
                    var verificationDeadline,
                        course = this.course;

                    // No validation is needed for empty values or seats not linked to courses.
                    if (_.isEmpty(value) || !course) {
                        return;
                    }

                    // Determine if the supplied expiration date occurs after the course verification deadline.
                    verificationDeadline = course.get('verification_deadline');
                    if (verificationDeadline && !moment(value).isBefore(verificationDeadline)) {
                        return gettext('The upgrade deadline must occur BEFORE the verification deadline.');
                    }
                }
            },

            // TODO Determine how to use the extended seatType attribute of child classes with Backbone.Relational
            // http://backbonerelational.org/#RelationalModel-subModelTypes
            getSeatType: function () {
                switch (this.get('certificate_type')) {
                    case 'verified':
                    {
                        return 'verified';
                    }
                    case 'credit':
                        return 'credit';
                    case 'professional':
                    case 'no-id-professional':
                        return 'professional';
                    case 'honor':
                        return 'honor';
                    default:
                        return 'audit';
                }
            },

            getSeatTypeDisplayName: function () {
                switch (this.get('certificate_type')) {
                    case 'verified':
                        return gettext('Verified');
                    case 'credit':
                        return gettext('Credit');
                    case 'professional':
                    case 'no-id-professional':
                        return gettext('Professional');
                    case 'honor':
                        return gettext('Honor');
                    default:
                        return gettext('Audit');
                }
            },

            getCertificateDisplayName: function () {
                switch (this.get('certificate_type')) {
                    case 'verified':
                    case 'credit':
                        return gettext('Verified Certificate');

                    case 'professional':
                    case 'no-id-professional':
                        return gettext('Professional Certificate');

                    case 'honor':
                        return gettext('Honor Certificate');

                    default:
                        return '(' + gettext('No Certificate') + ')';
                }
            }
        });
    }
);

define([
        'models/product_model'
    ],
    function (ProductModel) {
        'use strict';

        return ProductModel.extend({
            defaults: {
                certificate_type: null,
                expires: null,
                id_verification_required: null,
                price: 0,
                product_class: 'Seat'
            },

            validation: {
                // TODO Determine how to set this to the model's default.
                //certificate_type: {
                //    required: true
                //},
                price: {
                    required: true
                },
                product_class: {
                    oneOf: ['Seat']
                }
            },

            // TODO Determine how to use the extended seatType attribute of child classes with Backbone.Relational
            // http://backbonerelational.org/#RelationalModel-subModelTypes
            getSeatType: function () {
                switch (this.get('certificate_type')) {
                    case 'verified':
                        return 'verified';
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

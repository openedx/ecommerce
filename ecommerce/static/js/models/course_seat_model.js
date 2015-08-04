define([
        'backbone-super',
        'models/product_model'
    ],
    function (BackboneSuper,
              ProductModel) {
        'use strict';

        return ProductModel.extend({
            defaults: {
                certificate_type: null,
                expires: null,
                id_verification_required: null,
                price: null,
                product_class: 'Seat'
            },

            validation: {
                certificate_type: {
                    required: true
                },
                price: {
                    required: true
                },
                product_class: {
                    oneOf: ['Seat']
                }
            },

            getSeatType: function () {
                switch (this.get('certificate_type')) {
                    case 'verified':
                        return gettext('Verified');
                    case 'credit':
                        return gettext('Credit');
                    case 'professional':
                    case 'no-id-professional':
                        return gettext('Professional');
                    default:
                        return gettext('Honor');
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

                    default:
                        return gettext('Honor Certificate');
                }
            }
        });
    }
);

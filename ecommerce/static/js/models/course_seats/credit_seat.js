define([
        'models/course_seats/course_seat',
        'ecommerce'
    ],
    function (CourseSeat,
              ecommerce) {
        'use strict';

        return CourseSeat.extend({
            defaults: _.extend({}, CourseSeat.prototype.defaults,
                {
                    certificate_type: 'credit',
                    id_verification_required: true,
                    price: 0,
                    credit_provider: null,
                    credit_hours: null
                }
            ),

            validation: _.extend({}, CourseSeat.prototype.validation,
                {
                    credit_provider: function (value) {
                        if (!value) {
                            return gettext('All credit seats must have a credit provider.');
                        }

                        if (!ecommerce.credit.providers.findWhere({id: value})) {
                            return gettext('Please select a valid credit provider.');
                        }
                    },
                    credit_hours: {
                        required: true,
                        pattern: 'number',
                        min: 0,
                        msg: gettext('All credit seats must designate a number of credit hours.')
                    }
                }
            )
        }, {seatType: 'credit'});
    }
);

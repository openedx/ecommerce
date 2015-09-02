define([
        'jquery',
        'backbone',
        'backbone.validation',
        'backbone.stickit',
        'underscore',
        'underscore.string',
        'utils/utils'
    ],
    function ($,
              Backbone,
              BackboneValidation,
              BackboneStickit,
              _,
              _s,
              Utils) {
        'use strict';

        return Backbone.View.extend({
            idVerificationRequired: false,
            seatType: null,
            template: null,

            bindings: {
                'input[name=certificate_type]': 'certificate_type',
                'input[name=price]': {
                    observe: 'price',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=expires]': {
                    observe: 'expires',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=id_verification_required]': {
                    observe: 'id_verification_required',
                    onSet: 'cleanIdVerificationRequired'
                }
            },

            className: function () {
                return 'row ' + this.seatType + ' course-seat';
            },

            initialize: function () {
                Utils.bindValidation(this);
            },

            render: function () {
                this.$el.html(this.template(this.model.attributes));
                this.stickit();

                return this;
            },

            cleanIdVerificationRequired: function (val) {
                return _s.toBoolean(val);
            }
        });
    }
);

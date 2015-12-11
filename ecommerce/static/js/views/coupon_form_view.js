// jscs:disable requireCapitalizedConstructors

define([
        'jquery',
        'backbone',
        'backbone.super',
        'backbone.validation',
        'backbone.stickit',
        'underscore',
        'underscore.string',
        'text!templates/coupon_form.html',
        'views/form_view'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              _,
              _s,
              CouponFormTemplate,
              FormView) {
        'use strict';

        return FormView.extend({
            tagName: 'form',

            className: 'coupon-form-view',

            template: _.template(CouponFormTemplate),

            codeTypes: [
                {
                    value: 'discount',
                    label: gettext('Discount Code')
                },
                {
                    value: 'enrollment',
                    label: gettext('Enrollment Code'),
                },
            ],

            voucherTypes: [
                {
                    value: 'Single use',
                    label: gettext('Can be used once by one customer')
                },
                {
                    value: 'Multi-use',
                    label: gettext('Can be used multiple times by multiple customers'),
                },
                {
                    value: 'Once per customer',
                    label: gettext('Can only be used once per customer')
                }
            ],

            bindings: {
                'input[name=title]': {
                    observe: 'title'
                },
                'select[name=seat_type]': {
                    observe: 'seat_type',
                    selectOptions: {
                        collection: function() {
                            return this.model.get('seatTypes') || [];
                        }
                    }
                },
                'select[name=code_type]': {
                    observe: 'code_type',
                    selectOptions: {
                        collection: function() {
                            return this.codeTypes;
                        }
                    }
                },
                'select[name=voucher_type]': {
                    observe: 'voucher_type',
                    selectOptions: {
                        collection: function() {
                            return this.voucherTypes;
                        }
                    }
                },
                'input[name=benefit_type]': {
                    observe: 'benefit_type'
                },
                '.benefit-addon': {
                    observe: 'benefit_type',
                    onGet: function (val) {
                        if (val === 'Percentage') {
                            return '%';
                        }
                        else if (val === 'Fixed') {
                            return '$';
                        }
                        return '';
                    }
                },
                'input[name=benefit_value]': {
                    observe: 'benefit_value'
                },
                'input[name=client_username]': {
                    observe: 'client_username'
                },
                'input[name=course_id]': {
                    observe: 'course_id'
                },
                'input[name=quantity]': {
                    observe: 'quantity'
                },
                'input[name=price]': {
                    observe: 'price'
                },
                'input[name=start_date]': {
                    observe: 'start_date'
                },
                'input[name=end_date]': {
                    observe: 'end_date'
                },
                'input[name=code]': {
                    observe: 'code'
                }
            },

            initialize: function (options) {
                this.alertViews = [];
                this.editing = options.editing || false;

                this.listenTo(this.model, 'change:code_type', this.toggleFields);
                this.listenTo(this.model, 'change:voucher_type', this.toggleFields);

                this._super();
            },

            toggleFields: function() {
                var formGroup = function (sel) {
                    return this.$el.find(sel).closest('.form-group');
                }.bind(this);

                var codeType = this.model.get('code_type');
                var voucherType = this.model.get('voucher_type');

                if (codeType === 'discount') {
                    formGroup('[name=price]').addClass('hidden');
                    formGroup('[name=benefit_value]').removeClass('hidden');
                }
                // enrollment
                else {
                    formGroup('[name=price]').removeClass('hidden');
                    formGroup('[name=benefit_value]').addClass('hidden');
                }

                // When creating a discount show the CODE field for both (they are both multi-use)
                //     - Multiple times by multiple customers
                //     - Once per customer
                if (codeType === 'discount' && voucherType !== 'Single use') {
                    formGroup('[name=code]').removeClass('hidden');
                }
                else {
                    formGroup('[name=code]').addClass('hidden');
                }

                // The only time we allow for a generation of multiple codes is
                // when they are of type single use.
                if (voucherType === 'Single use') {
                    formGroup('[name=quantity]').removeClass('hidden');
                }
                else {
                    formGroup('[name=quantity]').addClass('hidden');
                }
            },

            /**
             * Navigate to coupon list on save (overrides default behaviour).
             */
            saveSuccess: function () {
                this.goTo('/');
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));
                this.stickit();

                // Avoid the need to create this jQuery object every time an alert has to be rendered.
                this.$alerts = this.$el.find('.alerts');

                this.model.set('code_type', this.codeTypes[0].value);
                this.model.set('voucher_type', this.voucherTypes[0].value);
                this.model.set('benefit_type', 'Percentage');

                this._super();
                return this;
            }

        });
    }
);

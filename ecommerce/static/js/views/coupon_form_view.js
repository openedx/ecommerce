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
        'views/alert_view',
        'utils/utils'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              _,
              _s,
              CouponFormTemplate,
              AlertView,
              Utils) {
        'use strict';

        return Backbone.View.extend({
            tagName: 'form',

            className: 'coupon-form-view',

            template: _.template(CouponFormTemplate),

            events: {
                'submit': 'submit'
            },

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

                // Enable validation
                Utils.bindValidation(this);
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

            remove: function () {
                Backbone.Validation.unbind(this);

                this.clearAlerts();

                return this._super();
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

                return this;
            },

            /**
             * Renders alerts that will appear at the top of the page.
             *
             * @param {String} level - Severity of the alert. This should be one of success, info, warning, or danger.
             * @param {Sring} message - Message to display to the user.
             */
            renderAlert: function (level, message) {
                var view = new AlertView({level: level, title: gettext('Error!'), message: message});

                view.render();
                this.$alerts.append(view.el);
                this.alertViews.push(view);

                $('body').animate({
                    scrollTop: this.$alerts.offset().top
                }, 500);

                this.$alerts.focus();

                return this;
            },

            /**
             * Remove all alerts currently on display.
             */
            clearAlerts: function () {
                _.each(this.alertViews, function (view) {
                    view.remove();
                });

                this.alertViews = [];

                return this;
            },

            /**
             * Returns the value of an input field.
             *
             * @param {String} name - Name of the field whose value should be returned
             * @returns {*} - Value of the field.
             */
            getFieldValue: function (name) {
                return this.$(_s.sprintf('input[name=%s]', name)).val();
            },

            /**
             * Submits the form data to the server.
             *
             * If client-side validation fails, data will NOT be submitted. Server-side errors will result in an
             * alert being rendered. If submission succeeds, the user will be redirected to the course detail page.
             *
             * @param e
             */
            submit: function (e) {
                var $buttons,
                    $submitButton,
                    btnDefaultText,
                    self = this,
                    btnSavingContent = '<i class="fa fa-spinner fa-spin" aria-hidden="true"></i> ' +
                        gettext('Saving...');

                e.preventDefault();

                // Validate the input and display a message, if necessary.
                if (!this.model.isValid(true)) {
                    this.clearAlerts();
                    this.renderAlert('danger', gettext('Please complete all required fields.'));
                    return;
                }

                $buttons = this.$el.find('.form-actions .btn');
                $submitButton = $buttons.filter('button[type=submit]');

                // Store the default button text, and replace it with the saving state content.
                btnDefaultText = $submitButton.text();
                $submitButton.html(btnSavingContent);

                // Disable all buttons by setting the attribute (for <button>) and class (for <a>)
                $buttons.attr('disabled', 'disabled').addClass('disabled');

                this.model.save({
                    complete: function () {
                        // Restore the button text
                        $submitButton.text(btnDefaultText);

                        // Re-enable the buttons
                        $buttons.removeAttr('disabled').removeClass('disabled');
                    },
                    success: function () {
                        self.goTo('/');
                    },
                    error: function (model, response) {
                        var message = gettext('An error occurred while saving the data.');

                        if (response.responseJSON && response.responseJSON.error) {
                            message = response.responseJSON.error;

                            // Log the error to the console for debugging purposes
                            console.error(message);
                        } else {
                            // Log the error to the console for debugging purposes
                            console.error(response.responseText);
                        }

                        self.clearAlerts();
                        self.renderAlert('danger', message);
                        self.$el.animate({scrollTop: 0}, 'slow');
                    }
                });

                return this;
            }
        });
    }
);

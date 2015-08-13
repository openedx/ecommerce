// jscs:disable requireCapitalizedConstructors

define([
        'jquery',
        'backbone',
        'backbone.super',
        'backbone.validation',
        'backbone.stickit',
        'moment',
        'underscore',
        'underscore.string',
        'text!templates/course_form.html',
        'text!templates/_course_type_radio_field.html',
        'views/course_seat_form_fields/audit_course_seat_form_field_view',
        'views/course_seat_form_fields/honor_course_seat_form_field_view',
        'views/course_seat_form_fields/verified_course_seat_form_field_view',
        'views/course_seat_form_fields/professional_course_seat_form_field_view',
        'views/alert_view',
        'utils/course_utils'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              moment,
              _,
              _s,
              CourseFormTemplate,
              CourseTypeRadioTemplate,
              AuditCourseSeatFormFieldView,
              HonorCourseSeatFormFieldView,
              VerifiedCourseSeatFormFieldView,
              ProfessionalCourseSeatFormFieldView,
              AlertView,
              CourseUtils) {
        'use strict';

        // Extend the callbacks to work with Bootstrap.
        // See: http://thedersen.com/projects/backbone-validation/#callbacks
        _.extend(Backbone.Validation.callbacks, {
            valid: function (view, attr) {
                var $el = view.$('[name=' + attr + ']'),
                    $group = $el.closest('.form-group');

                $group.removeClass('has-error');
                $group.find('.help-block:first').html('').addClass('hidden');
            },
            invalid: function (view, attr, error) {
                var $el = view.$('[name=' + attr + ']'),
                    $group = $el.closest('.form-group');

                $group.addClass('has-error');
                $group.find('.help-block:first').html(error).removeClass('hidden');
            }
        });

        return Backbone.View.extend({
            tagName: 'form',

            className: 'course-form-view',

            template: _.template(CourseFormTemplate),

            courseTypeRadioTemplate: _.template(CourseTypeRadioTemplate),

            courseTypes: {
                honor: {
                    type: 'honor',
                    displayName: gettext('Free (Honor)'),
                    helpText: gettext('Free honor track with Honor Certificate')
                },
                verified: {
                    type: 'verified',
                    displayName: gettext('Verified'),
                    helpText: gettext('Paid certificate track with initial verification and Verified Certificate')
                },
                professional: {
                    type: 'professional',
                    displayName: gettext('Professional Education'),
                    helpText: gettext('Paid certificate track with initial verification and Professional ' +
                        'Education Certificate')
                },
                credit: {
                    type: 'credit',
                    displayName: gettext('Credit'),
                    helpText: gettext('Paid certificate track with initial verification and Verified Certificate, ' +
                        'and option to buy credit')
                }
            },

            // Map course seats to view classes
            courseSeatViewMappings: {
                audit: AuditCourseSeatFormFieldView,
                honor: HonorCourseSeatFormFieldView,
                verified: VerifiedCourseSeatFormFieldView,
                professional: ProfessionalCourseSeatFormFieldView
            },

            events: {
                'submit': 'submit'
            },

            bindings: {
                'input[name=name]': {
                    observe: 'name',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=id]': {
                    observe: 'id',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=type]': {
                    observe: 'type',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=verification_deadline]': {
                    observe: 'verification_deadline',
                    setOptions: {
                        validate: true
                    }
                }
            },

            initialize: function (options) {
                this.alertViews = [];
                this.courseSeatViews = {};
                this.editing = options.editing || false;

                this.listenTo(this.model, 'change:type', this.renderCourseSeats);
                this.listenTo(this.model, 'change:type change:id_verification_required',
                    this.renderVerificationDeadline);

                // Listen for the sync event so that we can keep track of the original course type.
                // This helps us determine which course types the course can be upgraded to.
                if (this.editing) {
                    this.setLockedCourseType();
                }

                // Enable validation
                Backbone.Validation.bind(this);
            },

            remove: function () {
                Backbone.Validation.unbind(this);

                this.clearAlerts();

                _.each(this.courseSeatViews, function (view) {
                    view.remove();
                }, this);

                this.courseSeatViews = {};

                return this._super();
            },

            /**
             * Returns the course types that can be selected in the UI.
             *
             * @returns {Array}
             */
            getActiveCourseTypes: function () {
                var activeCourseTypes,
                    courseType = this.editing ? this.lockedCourseType : this.model.get('type');

                switch (courseType) {
                    case 'honor':
                        activeCourseTypes = ['honor', 'verified', 'credit'];
                        break;
                    case 'verified':
                        activeCourseTypes = ['verified', 'credit'];
                        break;
                    case 'professional':
                        activeCourseTypes = ['professional'];
                        break;
                    case 'credit':
                        activeCourseTypes = ['credit'];
                        break;
                    default:
                        activeCourseTypes = ['honor', 'verified', 'professional', 'credit'];
                        break;
                }

                // TODO Activate credit seat
                var index = activeCourseTypes.indexOf('credit');
                if (index > -1) {
                    activeCourseTypes.splice(index, 1);
                }

                return activeCourseTypes;
            },

            setLockedCourseType: function () {
                this.lockedCourseType = this.model.get('type');
                this.renderCourseTypes();
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));

                // Render the remaining form fields, which are dependent on the parent template.
                this.renderCourseTypes();
                this.renderCourseSeats();
                this.renderVerificationDeadline();

                this.stickit();

                return this;
            },

            /**
             * Renders the course type
             */
            renderCourseTypes: function () {
                var $courseTypesContainer,
                    html = '',
                    activeCourseTypes = this.getActiveCourseTypes();

                // Render the course type radio fields
                $courseTypesContainer = this.$el.find('.course-types');

                _.each(this.courseTypes, function (data, courseType) {
                    data.disabled = !_.contains(activeCourseTypes, courseType);
                    data.checked = (this.model.get('type') === courseType);
                    html += this.courseTypeRadioTemplate(data);
                }, this);

                $courseTypesContainer.html(html);
                this.delegateEvents();

                return this;
            },

            /**
             * Displays, or hides, the verification deadline based on the course type.
             */
            renderVerificationDeadline: function () {
                var $verificationDeadline = this.$el.find('.verification-deadline');

                // TODO Make this display a bit smoother with a slide.
                $verificationDeadline.toggleClass('hidden', !this.model.isIdVerified());

                return this;
            },

            /**
             * Renders the course seats based upon the course model's type field.
             */
            renderCourseSeats: function () {
                var $courseSeats,
                    $courseSeatsContainer = this.$el.find('.course-seats'),
                    activeSeats = this.model.validSeatTypes();

                // Display a helpful message if the user has not yet selected a course type.
                if (activeSeats.length < 1) {
                    activeSeats = ['empty'];
                } else {

                    _.each(CourseUtils.orderSeatTypesForDisplay(activeSeats), function (seatType) {
                        var model,
                            viewClass,
                            view = this.courseSeatViews[seatType];

                        if (!view) {
                            model = this.model.getOrCreateSeat(seatType);
                            viewClass = this.courseSeatViewMappings[seatType];

                            if (viewClass && model) {
                                /*jshint newcap: false */
                                view = new viewClass({model: model});
                                /*jshint newcap: true */
                                view.render();

                                this.courseSeatViews[seatType] = view;
                                $courseSeatsContainer.append(view.el);
                            }
                        }
                    }, this);
                }

                // Retrieve these after any new renderings.
                $courseSeats = $courseSeatsContainer.find('.course-seat');

                // Hide all seats
                $courseSeats.hide();

                _.each(activeSeats, function (seat) {
                    $courseSeats.filter('.' + seat).show();
                });

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
                this.$el.find('.alerts').append(view.el);
                this.alertViews.push(view);

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
                // TODO DRY: Find a way to better share this with CourseSeatFormFieldView.
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
                    success: function (model) {
                        self.goTo(model.id);
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

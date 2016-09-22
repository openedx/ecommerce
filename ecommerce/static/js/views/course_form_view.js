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
        'collections/product_collection',
        'text!templates/_alert_div.html',
        'text!templates/course_form.html',
        'text!templates/_course_type_radio_field.html',
        'views/course_seat_form_fields/audit_course_seat_form_field_view',
        'views/course_seat_form_fields/verified_course_seat_form_field_view',
        'views/course_seat_form_fields/professional_course_seat_form_field_view',
        'views/course_seat_form_fields/credit_course_seat_form_field_view',
        'views/form_view',
        'utils/course_utils',
        'utils/utils'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              moment,
              _,
              _s,
              ProductCollection,
              AlertDivTemplate,
              CourseFormTemplate,
              CourseTypeRadioTemplate,
              AuditCourseSeatFormFieldView,
              VerifiedCourseSeatFormFieldView,
              ProfessionalCourseSeatFormFieldView,
              CreditCourseSeatFormFieldView,
              FormView,
              CourseUtils,
              Utils) {
        'use strict';

        return FormView.extend({
            tagName: 'form',

            className: 'course-form-view',

            template: _.template(CourseFormTemplate),

            courseTypeRadioTemplate: _.template(CourseTypeRadioTemplate),

            courseTypes: {
                audit: {
                    type: 'audit',
                    displayName: gettext('Free (Audit)'),
                    helpText: gettext('Free audit track. No certificate.')
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
                        'and option to purchase credit')
                }
            },

            // Map course seats to view classes
            courseSeatViewMappings: {
                audit: AuditCourseSeatFormFieldView,
                verified: VerifiedCourseSeatFormFieldView,
                professional: ProfessionalCourseSeatFormFieldView,
                credit: CreditCourseSeatFormFieldView
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
                },
                'input[name=honor_mode]': {
                    observe: 'honor_mode',
                    setOptions: {
                        validate: true
                    },
                    onSet: 'cleanHonorMode'
                },
                'input[name=create_enrollment_code]': {
                    observe: 'create_enrollment_code'
                }
            },

            initialize: function (options) {
                this.courseSeatViews = {};
                this.editing = options.editing || false;

                this.listenTo(this.model, 'change:type', this.renderCourseSeats);
                this.listenTo(this.model, 'change:type change:id_verification_required',
                    this.renderVerificationDeadline);
                this.listenTo(this.model, 'change:type change:honor_mode',
                    this.renderHonorMode);
                this.listenTo(this.model, 'change:id' , this.validateCourseID);
                this.listenTo(this.model, 'change:type', this.toggleBulkEnrollmentField);

                // Listen for the sync event so that we can keep track of the original course type.
                // This helps us determine which course types the course can be upgraded to.
                if (this.editing) {
                    this.setLockedCourseType();
                }
                this._super();
            },

            remove: function () {
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
                    case 'audit':
                        activeCourseTypes = ['audit', 'verified', 'credit'];
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
                        activeCourseTypes = ['audit', 'verified', 'professional', 'credit'];
                        break;
                }

                return activeCourseTypes;
            },

            setLockedCourseType: function () {
                this.lockedCourseType = this.model.get('type');
            },

            cleanHonorMode: function (val) {
                return _s.toBoolean(val);
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));

                // Render the remaining form fields, which are dependent on the parent template.
                this.renderCourseTypes();
                this.renderCourseSeats();
                this.renderVerificationDeadline();
                this.renderHonorMode();
                this.disableHonorMode();
                this.$('.fields:first').before(AlertDivTemplate);

                this.stickit();

                this._super();

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
             * Displays, or hides, the honor mode based on the course type.
             */
            renderHonorMode: function () {
                var $honorModeContainer = this.$el.find('.honor-mode');

                $honorModeContainer.toggleClass('hidden', !this.model.includeHonorMode());

                return this;
            },

            /**
             * Makes honor mode read only if editing an existing course.
             */
            disableHonorMode: function() {
                var $honorModeRadioButtons = this.$el.find('input[name=honor_mode]');

                if( this.model.seats().length > 0 ){
                    $honorModeRadioButtons.attr('disabled', true);
                }
            },

            /**
             * Renders the course seats based upon the course model's type field.
             */
            renderCourseSeats: function () {
                var $courseSeats,
                    $courseSeatsContainer = this.$el.find('.course-seats'),
                    activeSeats = this.model.activeSeatTypes();

                // Display a helpful message if the user has not yet selected a course type.
                if (activeSeats.length < 1) {
                    activeSeats = ['empty'];
                } else {
                    _.each(CourseUtils.orderSeatTypesForDisplay(activeSeats), function (seatType) {
                        var seats,
                            viewClass,
                            view = this.courseSeatViews[seatType];

                        if (!view) {
                            seats = this.model.getOrCreateSeats(seatType);
                            // seats = new ProductCollection(this.model.getOrCreateSeats(seatType));
                            viewClass = this.courseSeatViewMappings[seatType];

                            if (viewClass && seats.length > 0) {
                                /*jshint newcap: false */
                                if (_.isEqual(seatType, 'credit')) {
                                    seats = new ProductCollection(seats);
                                    view = new viewClass({collection: seats, course: this.model});
                                } else {
                                    view = new viewClass({model: seats[0]});
                                }

                                this.$el.find('.course-seat.empty').addClass('hidden');
                                /*jshint newcap: true */
                                view.render();

                                this.courseSeatViews[seatType] = view;
                                $courseSeatsContainer.append(view.el);
                            }
                        }
                    }, this);
                }

                // Retrieve these after any new renderings.
                $courseSeats = $courseSeatsContainer.find('.row');

                // Hide all seats
                $courseSeats.hide();

                _.each(activeSeats, function (seat) {
                    $courseSeats.filter('.' + seat).show();
                });

                // Add date picker
                Utils.addDatePicker(this);

                return this;
            },

            /**
             * Toggle the bulk enrollment checkbox. Hidden only for audit mode.
             */
            toggleBulkEnrollmentField: function() {
                var bulk_enrollment_field = this.$('[name=create_enrollment_code]'),
                    form_group = bulk_enrollment_field.closest('.form-group');
                $.ajax({
                    url: '/api/v2/siteconfiguration/',
                    method: 'get',
                    contentType: 'application/json',
                    async: false,
                    success: this.onSuccess.bind(this)
                });

                if (this.$('[name=type]:checked').val() === 'audit') {
                    bulk_enrollment_field.prop('checked', false).trigger('change');
                    form_group.addClass('hidden');
                } else {
                    form_group.removeClass('hidden');
                }
            },

            onSuccess: function(data) {
                var site_configuration;
                site_configuration = _.find(data.results, function(item) {
                    return item.site.domain === window.location.host;
                }) || {};
                if (!site_configuration.enable_enrollment_codes) {
                    this.$('[name=create_enrollment_code]').attr('disabled', true);
                }
            }
        });
    }
);

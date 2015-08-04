define([
        'jquery',
        'backbone',
        'backbone-super',
        'backbone-validation',
        'backbone.stickit',
        'underscore',
        'underscore.string',
        'models/course_seat_model',
        'text!templates/course_form.html',
        'text!templates/_course_type_radio_field.html',
        'views/course_seat_form_fields/honor_course_seat_form_field_view',
        'views/course_seat_form_fields/verified_course_seat_form_field_view',
        'views/course_seat_form_fields/professional_course_seat_form_field_view',
        'views/alert_view',
        'jquery-cookie'
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              _,
              _s,
              CourseSeat,
              CourseFormTemplate,
              CourseTypeRadioTemplate,
              HonorCourseSeatFormFieldView,
              VerifiedCourseSeatFormFieldView,
              ProfessionalCourseSeatFormFieldView,
              AlertView,
              cookie) {
        'use strict';

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
                    helpText: gettext('Paid certificate track with initial verification and Professional Education Certificate')
                },
                credit: {
                    type: 'credit',
                    displayName: gettext('Credit'),
                    helpText: gettext('Paid certificate track with initial verification and Verified Certificate, and option to buy credit')
                }
            },

            // Map course types to the available seats
            courseTypeSeatMapping: {
                honor: ['honor'],
                verified: ['honor', 'verified'],
                professional: ['professional'],
                credit: ['honor', 'verified', 'credit']
            },

            // TODO Activate credit
            courseSeatTypes: ['honor', 'verified', 'professional'],

            // Map course seats to view classes
            courseSeatViewMappings: {
                honor: HonorCourseSeatFormFieldView,
                verified: VerifiedCourseSeatFormFieldView,
                professional: ProfessionalCourseSeatFormFieldView
            },


            events: {
                'change input[name=type]': 'changedCourseType',
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
                }
            },

            initialize: function (options) {
                this.alertViews = [];
                this.courseSeatViews = {};
                this.editing = options.editing || false;

                this.listenTo(this.model, 'change:type', this.renderCourseSeats);
                this.listenTo(this.model, 'change:products', this.updateCourseSeatModels);

                // Listen for the sync event so that we can keep track of the original course type.
                // This helps us determine which course types the course can be upgraded to.
                if (this.editing) {
                    this.listenTo(this.model, 'sync', this.setLockedCourseType);
                }

                Backbone.Validation.bind(this, {
                    forceUpdate: !this.editing,
                    valid: function (view, attr, selector) {
                        var $el = view.$('[name=' + attr + ']'),
                            $group = $el.closest('.form-group');

                        $group.removeClass('has-error');
                        $group.find('.help-block:first').html('').addClass('hidden');
                    },
                    invalid: function (view, attr, error, selector) {
                        var $el = view.$('[name=' + attr + ']'),
                            $group = $el.closest('.form-group');

                        $group.addClass('has-error');
                        $group.find('.help-block:first').html(error).removeClass('hidden');
                    }
                });
            },

            remove: function () {
                Backbone.Validation.unbind(this);

                this.clearAlerts();

                _.each(this.courseSeatViews, function (view, seatType) {
                    view.remove();
                }, this);

                this.courseSeatViews = {};

                return this._super();
            },

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

                this.stickit();

                return this;
            },

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
            },

            updateCourseSeatModels: function () {
                _.each(this.model.getSeats(), function (seat, seatType) {
                    var view = this.courseSeatViews[seatType];

                    if (view) {
                        view.model = seat;
                        view.render();
                    }
                }, this);
            },

            renderCourseSeats: function () {
                var $courseSeats,
                    seats = this.model.getSeats(),
                    $courseSeatsContainer = this.$el.find('.course-seats'),
                    activeSeats = this.courseTypeSeatMapping[this.model.get('type')] || ['empty'];

                if (_.isEmpty(this.courseSeatViews)) {
                    _.each(this.courseSeatTypes, function (seatType) {
                        var view,
                            price = seatType === 'honor' ? 0 : null,
                            model = seats[seatType] || new CourseSeat({certificate_type: seatType, price: price}),
                            viewClass = this.courseSeatViewMappings[seatType];

                        if (viewClass) {
                            view = new viewClass({model: model});
                            view.render();
                            this.courseSeatViews[seatType] = view;
                            $courseSeatsContainer.append(view.el);
                        } else {
                            console.warn('No view class found for seat type: ' + seatType);
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
            },

            renderAlert: function (level, message) {
                var view = new AlertView({level: level, title: gettext('Error!'), message: message});
                view.render();
                this.$el.find('.alerts').append(view.el);
                this.alertViews.push(view);
            },

            clearAlerts: function () {
                _.each(this.alertViews, function (view) {
                    view.remove();
                });

                this.alertViews = [];
            },

            changedCourseType: function (e) {
                this.model.set('type', e.target.value);
                this.renderCourseSeats();
            },

            // TODO DRY: Find a way to better share this with CourseSeatFormFieldView.
            getFieldValue: function (name) {
                return this.$(_s.sprintf('input[name=%s]', name)).val();
            },

            submit: function (e) {
                var data,
                    activeSeatTypes,
                    validation,
                    errorMessages,
                    message,
                    view,
                    products = [];

                e.preventDefault();

                // Validate the input and display a message, if necessary.

                validation = this.model.validate();
                if (validation) {
                    errorMessages = _.map(_.values(validation), function (msg) {
                        return '<li>' + msg + '</li>';
                    });

                    message = _s.sprintf('Validation failed:<br><ul>%s</ul>', errorMessages.join('<br>'));
                    this.clearAlerts();
                    this.renderAlert('danger', message);
                    return;
                }

                // Get the product data
                activeSeatTypes = this.courseTypeSeatMapping[this.model.get('type')];

                _.each(activeSeatTypes, function (seatType) {
                    view = this.courseSeatViews[seatType];
                    view.updateModel();
                    products.push(view.model.toJSON());

                }, this);

                data = {
                    id: this.getFieldValue('id'),
                    name: this.getFieldValue('name'),
                    products: products
                };

                $.ajax({
                    contentType: 'application/json',
                    context: this,
                    data: JSON.stringify(data),
                    dataType: 'json',
                    headers: {'X-CSRFToken': $.cookie('ecommerce_csrftoken')},
                    method: 'POST',
                    url: '/api/v2/publication/',
                    success: function (data, textStatus, jqXHR) {
                        this.goTo(data.id);
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        this.renderAlert('danger', jqXHR.responseJSON.error);
                        this.$el.animate({scrollTop: 0}, 'slow');
                    }
                });
            }
        });
    }
);

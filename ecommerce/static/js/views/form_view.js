define([
    'jquery',
    'backbone',
    'backbone.super',
    'backbone.validation',
    'underscore',
    'underscore.string',
    'utils/alert_utils',
    'utils/utils'
],
    function($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              _,
              _s,
              AlertUtils,
              Utils) {
        'use strict';

        var FormView = Backbone.View.extend({
            tagName: 'form',

            events: {
                submit: 'submit'
            },

            updateWithPatch: true,

            initialize: function() {
                this.alertViews = [];

                if (this.editing && _.has(this, 'editableAttributes')) {
                    this.modelServerState = this.model.pick(this.editableAttributes);
                }

                // Enable validation
                Utils.bindValidation(this);
            },

            remove: function() {
                Backbone.Validation.unbind(this);

                AlertUtils.clearAlerts(this);
                return this._super(); // eslint-disable-line no-underscore-dangle
            },

            render: function() {
                // Avoid the need to create this jQuery object every time an alert has to be rendered.
                this.$alerts = this.$el.find('.alerts');
                return this;
            },

            validateCourseID: function() {
                var self = this;
                var courseIdInput = self.$('input[name=id]');
                courseIdInput.focusout(function() {
                    var courseId = courseIdInput.val();
                    self.checkCourseAlreadyExist(courseId);
                });
            },
            /**
             * Validate the courseId input if it already exists
             */
            checkCourseAlreadyExist: function(courseId) {
                var courseIDFound = false,
                    self = this,
                    url = '/api/v2/courses/' + courseId,
                    redirectedUrl = '/courses/' + courseId,
                    html = '<a href="' + redirectedUrl + '"> Click here to view the existing course</a>',
                    message = gettext('A course with the specified ID already exists.' + html);

                $.ajax({
                    url: url,
                    method: 'get',
                    contentType: 'application/json',
                    async: false,
                    success: function(data) {
                        if (data.id === courseId) {
                            AlertUtils.clearAlerts(self);
                            AlertUtils.renderAlert('danger', gettext('Error!'), message, self);
                            courseIDFound = true;
                        }
                    },
                    error: function(response) {
                        if (response.status === 404) {
                            AlertUtils.clearAlerts(self);
                        }
                    }
                });
                return courseIDFound;
            },

            /**
             * Navigate to a new page within the App.
             *
             * @param {String} fragment
             */
            goTo: function(fragment) {
                Backbone.history.navigate(fragment, {trigger: true});
            },

            /**
             * Callback to run on save success.
             */
            saveSuccess: function(model) {
                this.goTo(model.id);
            },

            /**
             * Submits the form data to the server.
             *
             * If client-side validation fails, data will NOT be submitted. Server-side errors will result in an
             * alert being rendered. If submission succeeds, the user will be redirected to the course detail page.
             *
             * @param e
             */
            submit: function(e) {
                var changedAttributes,
                    editableAttributes,
                    $buttons,
                    $submitButton,
                    btnDefaultText,
                    self = this,
                    courseId = $('input[name=id]').val(),
                    btnSavingContent = '<i class="fa fa-spinner fa-spin" aria-hidden="true"></i> ' +
                        gettext('Saving...'),
                    onSaveComplete,
                    onSaveError;

                e.preventDefault();

                // Validate the input and display a message, if necessary.
                if (!this.model.isValid(true)) {
                    AlertUtils.clearAlerts(self);
                    AlertUtils.renderAlert('danger', '', gettext('Please complete all required fields.'), self);
                    return undefined;
                } else if (courseId && !self.editing && self.checkCourseAlreadyExist(courseId)) {
                    return undefined;
                }

                $buttons = this.$el.find('.form-actions .btn');
                $submitButton = $buttons.filter('button[type=submit]');

                // Store the default button text, and replace it with the saving state content.
                btnDefaultText = $submitButton.text();
                $submitButton.html(btnSavingContent);

                // Disable all buttons by setting the attribute (for <button>) and class (for <a>)
                $buttons.attr('disabled', 'disabled').addClass('disabled');

                onSaveComplete = function() {
                    // Restore the button text
                    $submitButton.text(btnDefaultText);

                    // Re-enable the buttons
                    $buttons.removeAttr('disabled').removeClass('disabled');
                };

                onSaveError = function(model, response) {
                    var message = gettext('An error occurred while saving the data.');

                    if (response.responseJSON && response.responseJSON.error) {
                        message = response.responseJSON.error;

                        // Log the error to the console for debugging purposes
                        console.error(message); // eslint-disable-line no-console
                    } else {
                        // Log the error to the console for debugging purposes
                        console.error(response.responseText); // eslint-disable-line no-console
                    }

                    AlertUtils.clearAlerts(self);
                    AlertUtils.renderAlert('danger', gettext('Error!'), message, self);
                };

                if (this.editing && _.has(this, 'editableAttributes')) {
                    editableAttributes = this.model.pick(this.editableAttributes);
                    changedAttributes = _.omit(editableAttributes, function(value, key) {
                        return value === this.modelServerState[key];
                    }, this);

                    this.model.save(
                        changedAttributes,
                        {
                            complete: onSaveComplete,
                            error: onSaveError,
                            patch: this.updateWithPatch,
                            success: this.saveSuccess.bind(this)
                        }
                    );
                } else {
                    this.model.save(
                        null,
                        {
                            complete: onSaveComplete,
                            success: this.saveSuccess.bind(this),
                            error: onSaveError
                        }
                    );
                }

                return this;
            }
        });

        /**
         * Override Backbone.View.extend so that the child view inherits events.
         */
        FormView.extend = function(child) {
            var view = Backbone.View.extend.apply(this, arguments);
            view.prototype.events = _.extend({}, this.prototype.events, child.events);
            return view;
        };

        return FormView;
    }
);

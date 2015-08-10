define([
        'jquery',
        'underscore',
        'backbone'
    ],
    function ($, _, Backbone) {
        'use strict';

        return Backbone.View.extend({

            initialize: function () {
                this.checkEligibility();
            },

            checkEligibility: function () {
                var $courseDetails = $('#course-name'),
                    username = $courseDetails.data('username'),
                    courseKey = $courseDetails.data('course_key'),
                    self = this;

                this.collection.setUrl(username, courseKey);
                this.collection.fetch({
                        success: function (collection) {
                            self.renderEligibilityDate(collection);
                        },
                        error: function () {
                            self.toggleProviderContent(false);
                        }
                    }
                );
            },

            renderEligibilityDate: function (collection) {
                // For getting full month name, default lang is set to 'en-us',
                // It will be translated in django template

                var eligibilityData = collection.toJSON(),
                    deadline, formattedDate;

                if (eligibilityData.length) {
                    deadline = new Date(eligibilityData[0].deadline);
                    // TODO Use moment.format(). See http://momentjs.com/docs/#/displaying/.
                    formattedDate = deadline.toLocaleString('en-us', {month: 'long'}) + ' ' + deadline.getDay() + ',' +
                        deadline.getFullYear();
                    $('.eligibility-details').find('.deadline-date').text(formattedDate);
                    this.toggleProviderContent(true);
                } else {
                    this.toggleProviderContent(false);
                }
            },

            toggleProviderContent: function (isEnabled) {
                // On request failure hide provider panel and show error message.
                $('.provider-panel').toggleClass('hide', !isEnabled);
                $('.error-message').toggleClass('hide', isEnabled);
            }
        });
    }
);

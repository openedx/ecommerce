define([
        'backbone'
    ],
    function (Backbone) {
        'use strict';

        return {
            /**
             * Returns a Backbone model that can be used to test validation.
             *
             * @param {Boolean} valid - Indicates if the model should pass or fail validation.
             */
            getModelForValidation: function (valid) {
                return Backbone.Model.extend({
                    defaults: {
                        id: null,
                        category: {}
                    },

                    isValid: function () {
                        return valid;
                    },

                    validate: function () {
                        if (valid) {
                            return {};
                        }

                        return {error: 'Test model: validate always fails.'};
                    }
                });
            },

            /**
             * Returns a Boolean value that indicates whether a DOM element has a specific class.
             */
            toHaveClass: function () {
                return {
                    compare: function (actual, className) {
                        return { pass: $(actual).hasClass(className) };
                    }
                };
            },

            /**
              * Helper function to check if a form field is visible.
              */
            visibleElement: function(view, selector, groupSelector) {
                var formGroup = view.$(selector).closest(groupSelector);
                if (formGroup.length > 0) {
                    return !formGroup.hasClass('hidden');
                } else {
                    return false;
                }
            }
        };
    }
);

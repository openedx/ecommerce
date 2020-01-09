define([
    'backbone'
],
    function(Backbone) {
        'use strict';

        return {
            /**
             * Returns a Backbone model that can be used to test validation.
             *
             * @param {Boolean} valid - Indicates if the model should pass or fail validation.
             */
            getModelForValidation: function(valid) {
                return Backbone.Model.extend({
                    defaults: {
                        id: null,
                        category: {},
                        course_catalog: {}
                    },
                    catalogTypes: {
                        single_course: 'Single course',
                        multiple_courses: 'Multiple courses',
                        catalog: 'Catalog'
                    },

                    isValid: function() {
                        return valid;
                    },

                    validate: function() {
                        if (valid) {
                            return {};
                        }

                        return {error: 'Test model: validate always fails.'};
                    }
                });
            },

            /**
             * Helper function to return the closest form group.
             */
            formGroup: function(view, selector) {
                return view.$(selector).closest('.form-group');
            }
        };
    }
);

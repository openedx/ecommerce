define([
    'backbone',
    'underscore',
    'utils/utils',
    'backbone.super'
],
    function(Backbone,
              _,
              Utils) {
        'use strict';

        return Backbone.Collection.extend({
            initialize: function(models, options) {
                // NOTE (CCB): This is a hack to workaround an issue with Backbone.relational's reverseRelation
                // not working properly.
                if (options) {
                    this.course = options.course;
                }
            },

            /**
             * Validates the collection by iterating over the nested models.
             *
             * @return {Boolean} Boolean indicating if this Collection is valid.
             */
            isValid: function() {
                return Utils.areModelsValid(this.models);
            },

            set: function(models, options) {
                _.each(models, function(model) {
                    if (_.isObject(model)) {
                        model.course = this.course; // eslint-disable-line no-param-reassign
                    }
                }, this);

                this._super(models, options);
            }
        });
    }
);

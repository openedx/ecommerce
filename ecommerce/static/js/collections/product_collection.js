define([
        'backbone',
        'utils/utils'
    ],
    function (Backbone,
              Utils) {
        'use strict';

        return Backbone.Collection.extend({
            /**
             * Validates the collection by iterating over the nested models.
             *
             * @return {Boolean} Boolean indicating if this Collection is valid.
             */
            isValid: function () {
                return Utils.areModelsValid(this.models);
            }
        });
    }
);

define([
        'backbone'
    ],
    function (Backbone) {
        'use strict';

        return Backbone.Model.extend({
            urlRoot: '/api/v2/products/',

            initialize: function () {
                this.listenTo(this, 'fetch', this.populateAttributes);
            },

            populateAttributes: function() {

                this.clear();

                // Expose the nested attribute values as top-level attributes on the model
                this.get('attribute_values').forEach(function (av) {
                    this.set(av.name, av.value);
                }, this);
            }
        });
    }
);

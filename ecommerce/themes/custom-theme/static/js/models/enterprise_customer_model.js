/* istanbul ignore next */
define([
    'backbone',
    'backbone.relational'
],
    function(Backbone) {
        'use strict';

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/enterprise/customers',
            label: function() {
                return this.get('name');
            }
        });
    }
);

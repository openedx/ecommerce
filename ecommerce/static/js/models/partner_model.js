define([
        'backbone',
        'backbone.relational'
    ],
    function(Backbone, BackboneRelational) {
        'use strict';

        return Backbone.RelationalModel.extend({

            urlRoot: '/api/v2/partners/'

        });
    }
);

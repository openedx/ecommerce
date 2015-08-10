define([
        'backbone',
        'js/models/provider_model'
    ],
    function (Backbone, ProviderModel) {
        'use strict';

        return Backbone.Collection.extend({
                model: ProviderModel,
                /*jshint undef: false */
                url: lmsRootUrl + '/api/credit/v1/providers/',
                /*jshint undef: true */
                setUrl: function (providerIds) {
                    this.url += '?provider_ids=' + providerIds;
                }
            }
        );
    }
);

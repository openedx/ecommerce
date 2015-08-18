define([
        'jquery',
        'underscore',
        'backbone',
        'text!templates/credit_provider_details.html'
    ],
    function ($,
              _,
              Backbone,
              creditProviderTemplate) {
        'use strict';

        return Backbone.View.extend({
            template: _.template(creditProviderTemplate),

            initialize: function () {
                this.listenTo(this.collection, 'sync', this.render);
                this.collection.fetch();
            },

            render: function () {
                var provider;

                if (this.collection.length) {
                    // Currently we are assuming that we are having only one provider
                    provider = this.collection.at(0);
                    // TODO Get rid of this!
                    $('.title').find('.provider-name').text(provider.get('display_name'));
                    this.$el.html(this.template(provider.attributes));
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


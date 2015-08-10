define([
        'jquery',
        'underscore',
        'backbone',
        'text!templates/provider_details.html'
    ],
    function ($, _, Backbone, providerTemplate) {
        'use strict';

        return Backbone.View.extend({

            initialize: function () {
                this.getProviders();
            },

            getProviders: function () {
                var self = this;

                this.collection.setUrl(this.$el[0].dataset.providersIds);
                this.collection.fetch({
                        success: function (collection) {
                            self.renderProviderDetail(collection);
                        },
                        error: function () {
                            self.toggleProviderContent(false);
                        }
                    }
                );
            },

            renderProviderDetail: function (collection) {
                var providerData = collection.toJSON(),
                    template;

                if (providerData.length) {
                    // Currently we are assuming that we are having only one provider
                    template = _.template(providerTemplate);
                    $('.title').find('.provider-name').text(providerData[0].display_name);
                    this.$el.html(template(providerData[0]));
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


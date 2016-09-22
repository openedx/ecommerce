define([
        'backbone'
    ],
    function (Backbone) {
        'use strict';

        return Backbone.View.extend({

            events: {
                'change input[name=provider]': 'onProviderSelection'
            },

            render: function () {
                this.$el.find('input[name=provider]:first').click();
                return this;
            },

            onProviderSelection: function () {
                var $selectedProvider = this.$el.find('input[name=provider]:checked').closest('.provider');

                this.trigger('productSelected', {
                    sku: $selectedProvider.data('sku'),
                    price: $selectedProvider.data('price'),
                    discount: $selectedProvider.data('discount'),
                    new_price: $selectedProvider.data('new-price'),
                });

                // toggle 'selected' class for background color
                this.$el.find('.provider').removeClass('selected');
                $selectedProvider.addClass('selected');

                // toggle text of label between 'select' and 'selected'
                this.$el.find('.radio-button span').text(gettext('Select'));
                $selectedProvider.find('.radio-button span').text(gettext('Selected'));
            }
        });
    }
);

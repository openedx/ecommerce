define([
    'jquery',
    'backbone',
    'views/payment_button_view',
    'utils/utils',
    'views/provider_selection_view',
    'pages/page'
],
    function($,
              Backbone,
              PaymentButtonView,
              Utils,
              ProviderSelectionView,
              Page) {
        'use strict';

        return Page.extend({

            initialize: function() {
                var providerSelectionView = new ProviderSelectionView({el: '.provider-details'}),
                    paymentButtonView = new PaymentButtonView({el: '#payment-buttons'});

                this.listenTo(providerSelectionView, 'productSelected', function(data) {
                    paymentButtonView.setSku(data.sku);
                    // Update the display of the checkout total.
                    if (data.discount === 'None') {
                        this.$('span.total-price').text(data.price);
                    } else {
                        this.$('span.price').text(data.price);
                        this.$('span.discount').text(data.discount);
                        this.$('span.total-price').text(data.new_price);
                    }
                });

                // Render the payment buttons first, since the rendering of the provider selection will
                // select the first available product.
                paymentButtonView.render();
                providerSelectionView.render();
            }
        });
    }
);

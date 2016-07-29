require([
        'jquery',
        'views/basket_view',
        'views/checkout_button_view'
    ],
    function ($,
              BasketView,
              CheckoutButtonView) {
        'use strict';

        new BasketView({el: $('.basket')});
        new CheckoutButtonView({el: $('.payment-buttons')})
    }
);

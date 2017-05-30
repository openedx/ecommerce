require([
    'jquery',
    'pages/basket_page'
],
    function($,
              BasketPage) {
        'use strict';

        $(document).ready(function() {
            BasketPage.onReady();
        });
    }
);

require([
        'jquery',
        'pages/basket_page'
    ],
    function ($,
              BasketPage) {
        'use strict';

        $(document).ready(BasketPage.onReady);
    }
);

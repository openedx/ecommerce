require([
    'jquery',
    'pages/basket_page'
],
    function($,
              BasketPage) {
        'use strict';

        $(document).ready(function() {
            // TODO: Change to responsive javascript after this site turns into a MFE
            if (!window.location.href.split('discount_jwt=')[1]) {
                $.ajax({
                    url: window.lmsUrlRoot + '/api/discounts/course/' + window.courseKey,
                    xhrFields: {
                        withCredentials: true
                    }
                }).done(function(discount) {
                    if (discount.discount_applicable) {
                        window.location.replace(window.location.href + '?discount_jwt=' + discount.jwt)
                    };
                });
            }

            BasketPage.onReady();
        });
    }
);

require([
    'jquery',
    'pages/basket_page'
],
    function($,
              BasketPage) {
        'use strict';

        $(document).ready(function() {
            // TODO: Change to responsive javascript after this site turns into a MFE
            var oldUrl, indexOfFragment, discountString, newUrl;
            if (window.courseKey !== undefined && !window.location.href.split('discount_jwt=')[1]) {
                $.ajax({
                    url: window.lmsUrlRoot + '/api/discounts/course/' + window.courseKey,
                    xhrFields: {
                        withCredentials: true
                    }
                }).done(function(discount) {
                    if (discount.discount_applicable) {
                        oldUrl = window.location.href;
                        indexOfFragment = oldUrl.indexOf('#');
                        if (oldUrl.includes('?')) {
                            discountString = '&discount_jwt=' + discount.jwt;
                        } else {
                            discountString = '?discount_jwt=' + discount.jwt;
                        }
                        if (indexOfFragment > -1) {
                            newUrl = oldUrl.substring(0, indexOfFragment) +
                                     discountString +
                                     oldUrl.substring(indexOfFragment);
                        } else {
                            newUrl = oldUrl + discountString;
                        }

                        window.location.replace(newUrl);
                    }
                });
            }

            BasketPage.onReady();
        });
    }
);

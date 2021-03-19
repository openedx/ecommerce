define([
    'jquery'
],
    function($) {
        'use strict';

        function disableBackButton() {
            /*
             * This function uses the URL fragment to prevent users from accidentally
             * resubmitting the payment form by discouraging them from using their
             * browser's back button on this page. This is a necessary precaution
             * when dealing with CyberSource. For more, please see LEARNER-1671.
             */
            var initialHash = location.hash,
                // Deriving the replacement hash from a timestamp helps keep this
                // logic working as expected if a user uses the back button in their
                // browser to return to this page after the replacement hash has
                // been pushed onto the history stack.
                replacementHash = '#' + Date.now().toString(36),
                warningMessage = gettext(
                    'Caution! Using the back button on this page may cause you to be charged again.'
                );

            // We push the initial hash onto the top of the browser history stack.
            history.pushState(null, '', replacementHash);

            window.onhashchange = function() {
                if (location.hash === initialHash) {
                    // If the initial hash is popped off the history stack, alert
                    // the user that going back may cause them to be charged again,
                    // then push the initial hash back onto the history stack.
                    // eslint-disable-next-line no-alert
                    alert(warningMessage);

                    history.pushState(null, '', replacementHash);
                }
            };
        }

        function trackPurchase(orderId, totalAmount, currency, productIds) {
            window.analytics.track('Completed Purchase', {
                orderId: orderId,
                total: totalAmount,
                currency: currency,
                productIds: productIds
            });
        }

        function onReady() {
            var $el = $('#receipt-container'),
                currency = $el.data('currency'),
                orderId = $el.data('order-id'),
                totalAmount = $el.data('total-amount'),
                productIds = $el.data('product-ids');

            if ($el.data('back-button')) {
                disableBackButton();
            }

            if (orderId) {
                trackPurchase(orderId, totalAmount, currency, productIds);
            }
        }

        $(document).ready(onReady);

        return {
            onReady: onReady
        };
    }
);

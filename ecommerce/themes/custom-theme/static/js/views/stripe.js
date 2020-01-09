/* istanbul ignore next */
require([
    'jquery',
    'payment_processors/stripe'
], function($, StripeProcessor) {
    'use strict';

    $(document).ready(function() {
        StripeProcessor.init(window.StripeConfig);
    });
});

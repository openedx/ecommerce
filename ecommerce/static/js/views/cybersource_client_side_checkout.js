/* istanbul ignore next */
require([
    'jquery',
    'payment_processors/cybersource'
], function($, CyberSourceClient) {
    'use strict';

    $(document).ready(function() {
        CyberSourceClient.init(window.CyberSourceConfig);
    });
});

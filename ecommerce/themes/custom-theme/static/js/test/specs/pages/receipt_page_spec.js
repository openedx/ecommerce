define([
    'jquery',
    'pages/receipt_page',
    'utils/analytics_utils'
],
    function($,
              ReceiptPage,
              AnalyticsUtils) {
        'use strict';

        describe('Receipt Page', function() {
            beforeEach(function() {
                $('<script type="text/javascript">var initModelData = {};</script>').appendTo('body');
                $(
                    '<div id="receipt-container" data-order-id="ORDER_ID"></div>'
                ).appendTo('body');
                AnalyticsUtils.analyticsSetUp();

                /* eslint-disable */
                window.analytics = window.analytics || []; if (!analytics.initialize) if (analytics.invoked)window.console && console.error && console.error('Segment snippet included twice.'); else { analytics.invoked = !0; analytics.methods = ['trackSubmit', 'trackClick', 'trackLink', 'trackForm', 'pageview', 'identify', 'group', 'track', 'ready', 'alias', 'page', 'once', 'off', 'on']; analytics.factory = function(t) { return function() { var e = Array.prototype.slice.call(arguments); e.unshift(t); analytics.push(e); return analytics; }; }; for (var t = 0; t < analytics.methods.length; t++) { var e = analytics.methods[t]; analytics[e] = analytics.factory(e); }analytics.load = function(t) { var e = document.createElement('script'); e.type = 'text/javascript'; e.async = !0; e.src = (document.location.protocol === 'https:' ? 'https://' : 'http://') + 'cdn.segment.com/analytics.js/v1/' + t + '/analytics.min.js'; var n = document.getElementsByTagName('script')[0]; n.parentNode.insertBefore(e, n); }; analytics.SNIPPET_VERSION = '3.0.1'; }
                /* eslint-enable */
            });

            describe('onReady', function() {
                it('should not disable the back button if default values are used for data-back-button', function() {
                    ReceiptPage.onReady();

                    expect(location.hash).toEqual('');
                });

                it('should disable the back button if value of data-back-button is set', function() {
                    var receiptPage = document.getElementById('receipt-container');
                    receiptPage.setAttribute('data-back-button', 1);

                    ReceiptPage.onReady();

                    expect(location.hash).toContain('#');

                    history.back();

                    // This just confirms that there was no full page reload from hitting the back button
                    expect(location.hash).toEqual('');
                });

                it('should trigger track purchase', function() {
                    spyOn(window.analytics, 'track');

                    ReceiptPage.onReady();

                    expect(window.analytics.track).toHaveBeenCalled();
                });
            });
        });
    }
);

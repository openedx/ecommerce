define([
        'jquery',
        'utils/analytics_utils',
        'pages/coupon_offer_page',
        'models/tracking_model',
        'models/user_model',
        'views/analytics_view',
    ],
    function($,
             AnalyticsUtils,
             CouponOfferPage,
             TrackingModel,
             UserModel,
             AnalyticsView
             ) {
        'use strict';

        describe('Coupon offer page', function() {
            beforeEach(function() {
                $('<a href=""'+
                'id="PurchaseCertificate"'+
                'class="btn btn-success btn-purchase"'+
                'data-track-type="click"'+
                'data-track-event="edx.bi.ecommerce.coupons.accept_offer"'+
                'data-track-category="Coupons accepted offer"'+
                'data-course-id="{{ course.id }}">'+
                'Purchase Certificate'+
                '</a>').appendTo('body');
                $('<script type="text/javascript">var initModelData = {};</script>').appendTo('body');
            });

            afterEach(function () {
                $('body').empty();
            });

            describe('Analytics', function() {
                beforeEach(function () {
                    spyOn(TrackingModel.prototype, 'isTracking').and.callFake(function() {
                        return true;
                    });
                    spyOn(AnalyticsView.prototype, 'track');
                    AnalyticsUtils.analyticsSetUp();
                    new CouponOfferPage();
                });

                it('should trigger purchase certificate event', function() {
                    $('a#PurchaseCertificate').trigger('click');
                    expect(AnalyticsView.prototype.track).toHaveBeenCalledWith(
                        'edx.bi.ecommerce.coupons.accept_offer',
                        { category: 'Coupons accepted offer', type: 'click' }
                    );
                });
            });
        });
});

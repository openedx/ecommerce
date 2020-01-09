require([
    'backbone',
    'collections/category_collection',
    'collections/enterprise_customer_collection',
    'collections/enterprise_customer_catalogs_collection',
    'ecommerce',
    'routers/enterprise_coupon_router',
    'utils/navigate'
],
    function(Backbone,
              CategoryCollection,
              EnterpriseCustomerCollection,
              EnterpriseCustomerCatalogsCollection,
              ecommerce,
              CouponRouter,
              navigate) {
        'use strict';

        $(function() {
            var startApp = function() {
                var $app = $('#app'),
                    couponApp = new CouponRouter({$el: $app});
                couponApp.start();

                // Handle navbar clicks.
                $('a.navbar-brand').on('click', navigate);

                // Handle internal clicks
                $app.on('click', 'a', navigate);
            };

            ecommerce.coupons = ecommerce.coupons || {};
            ecommerce.coupons.categories = new CategoryCollection();
            ecommerce.coupons.categories.url = '/api/v2/coupons/categories/';

            ecommerce.coupons.enterprise_customers = new EnterpriseCustomerCollection();
            ecommerce.coupons.enterprise_customer_catalogs = new EnterpriseCustomerCatalogsCollection();

            $.when(
                ecommerce.coupons.categories.fetch()
            ).always(startApp());
        });
    }
);

require([
    'backbone',
    'collections/category_collection',
    'collections/catalog_collection',
    'collections/enterprise_customer_collection',
    'ecommerce',
    'routers/coupon_router',
    'utils/navigate'
],
    function(Backbone,
              CategoryCollection,
              CatalogCollection,
              EnterpriseCustomerCollection,
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

            ecommerce.coupons.catalogs = new CatalogCollection();

            ecommerce.coupons.enterprise_customers = new EnterpriseCustomerCollection();

            $.when(ecommerce.coupons.categories.fetch(),
                ecommerce.coupons.catalogs.fetch()
            ).always(startApp());
        });
    }
);

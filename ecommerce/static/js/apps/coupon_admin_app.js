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
            var $app = $('#app'),
                couponApp = new CouponRouter({$el: $app});

            ecommerce.coupons = ecommerce.coupons || {};
            ecommerce.coupons.categories = new CategoryCollection();
            ecommerce.coupons.categories.url = '/api/v2/coupons/categories/';
            ecommerce.coupons.categories.fetch({async: false});

            ecommerce.coupons.catalogs = new CatalogCollection();
            ecommerce.coupons.catalogs.fetch({async: false});

            ecommerce.coupons.enterprise_customers = new EnterpriseCustomerCollection();
            ecommerce.coupons.enterprise_customers.fetch({async: false});
            ecommerce.currency = {
                currencyCode: $app.data('currency-code'),
                currencySymbol: $app.data('currency-symbol')
            };

            couponApp.start();

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate);

            // Handle internal clicks
            $app.on('click', 'a', navigate);
        });
    }
);

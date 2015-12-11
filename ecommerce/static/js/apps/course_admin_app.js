require([
        'backbone',
        'routers/course_router',
        'collections/credit_provider_collection',
        'ecommerce',
        'utils/navigate'
    ],
    function (Backbone,
              CourseRouter,
              CreditProviderCollection,
              ecommerce,
              navigate) {
        'use strict';

        $(function () {
            var $app = $('#app'),
                courseApp = new CourseRouter({$el: $app});

            ecommerce.credit = ecommerce.credit || {};
            ecommerce.credit.providers = new CreditProviderCollection($app.data('credit-providers'));

            courseApp.start();

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate);

            // Handle internal clicks
            $app.on('click', 'a', navigate);
        });
    }
);

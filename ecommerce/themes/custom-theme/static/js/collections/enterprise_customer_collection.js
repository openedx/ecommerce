/* istanbul ignore next */
define([
    'backbone',
    'models/enterprise_customer_model'
],
    function(
        Backbone,
        EnterpriseCustomer) {
        'use strict';

        return Backbone.Collection.extend({
            model: EnterpriseCustomer,
            url: '/api/v2/enterprise/customers'
        });
    }
);

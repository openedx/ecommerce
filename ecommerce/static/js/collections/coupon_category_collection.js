define([
        'backbone',
        'underscore',
        'models/coupon_category'
    ],
    function (Backbone,
              _,
              CouponCategory) {
        'use strict';

        return Backbone.Collection.extend({
            model: CouponCategory,
            url: '/api/v2/categories/3/',
            parse: function (response) {
                return response.child.map(function(obj){
                    return {
                        value: obj.id,
                        label: gettext(obj.name),
                        selected: response.child.indexOf(obj) === 0
                    };
                });
            }
        });
    }
);
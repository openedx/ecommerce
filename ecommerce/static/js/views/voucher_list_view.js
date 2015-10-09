define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/voucher_list.html'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              voucherListViewTemplate) {

        'use strict';

        return Backbone.View.extend({
            className: 'voucher-list-view',

            template: _.template(voucherListViewTemplate),

            render: function () {
                this.$el.html(this.template);

                return this;
            },
        });
    }
);

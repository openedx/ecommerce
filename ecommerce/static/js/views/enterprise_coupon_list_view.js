define([
    'jquery',
    'views/coupon_list_view',
    'underscore',
    'moment',
    'text!templates/enterprise_coupon_list.html',
    'dataTablesBootstrap'
],
    function($,
              CouponListView,
              _,
              moment,
              EnterpriseCouponListViewTemplate) {
        'use strict';

        return CouponListView.extend({
            template: _.template(EnterpriseCouponListViewTemplate),
            linkTpl: _.template('<a href="/enterprise/coupons/<%= id %>/" class="coupon-title"><%= title %></a>'),
            url: '/api/v2/enterprise/coupons/?format=datatables',

            getTableColumns: function() {
                return [
                    {
                        title: gettext('Name'),
                        data: 'title',
                        fnCreatedCell: _.bind(function(nTd, sData, oData) {
                            $(nTd).html(this.linkTpl(oData));
                        }, this)
                    },
                    {
                        title: gettext('Created'),
                        data: 'date_created',
                        fnCreatedCell: function(nTd, sData, oData) {
                            $(nTd).html(moment(oData.date_created).format('MMMM DD, YYYY, h:mm A'));
                        }
                    },
                    {
                        title: gettext('Status'),
                        data: 'code_status',
                        orderable: false,
                        searchable: false
                    },
                    {
                        title: gettext('Client'),
                        data: 'client',
                        orderable: false,
                        searchable: false
                    },
                    {
                        title: gettext('Enterprise Customer'),
                        data: 'enterprise_customer',
                        orderable: false,
                        searchable: false
                    },
                    {
                        title: gettext('Enterprise Customer Catalog'),
                        data: 'enterprise_customer_catalog',
                        orderable: false,
                        searchable: false
                    },
                    {
                        title: gettext('Coupon Report'),
                        data: 'id',
                        fnCreatedCell: _.bind(function(nTd, sData, oData) {
                            $(nTd).html(this.downloadTpl(oData));
                        }, this),
                        orderable: false,
                        searchable: false
                    }
                ];
            }
        });
    }
);

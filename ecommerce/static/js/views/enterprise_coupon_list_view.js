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
                        data: 'dateCreated'
                    },
                    {
                        title: gettext('Status'),
                        data: 'codeStatus'
                    },
                    {
                        title: gettext('Client'),
                        data: 'client'
                    },
                    {
                        title: gettext('Enterprise Customer'),
                        data: 'enterpriseCustomer'
                    },
                    {
                        title: gettext('Enterprise Customer Catalog'),
                        data: 'enterpriseCustomerCatalog'
                    },
                    {
                        title: gettext('Coupon Report'),
                        data: 'id',
                        fnCreatedCell: _.bind(function(nTd, sData, oData) {
                            $(nTd).html(this.downloadTpl(oData));
                        }, this),
                        orderable: false
                    }
                ];
            },

            getRowData: function(coupon) {
                return {
                    client: coupon.get('client'),
                    codeStatus: coupon.get('code_status'),
                    enterpriseCustomer: coupon.get('enterprise_customer'),
                    enterpriseCustomerCatalog: coupon.get('enterprise_customer_catalog'),
                    id: coupon.get('id'),
                    title: coupon.get('title'),
                    dateCreated: moment(coupon.get('date_created')).format('MMMM DD, YYYY, h:mm A')
                };
            }
        });
    }
);

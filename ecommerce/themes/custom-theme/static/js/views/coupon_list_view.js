define([
    'jquery',
    'backbone',
    'underscore',
    'underscore.string',
    'moment',
    'text!templates/coupon_list.html',
    'dataTablesBootstrap'
],
    function($,
              Backbone,
              _,
              _s,
              moment,
              CouponListViewTemplate) {
        'use strict';

        return Backbone.View.extend({
            className: 'coupon-list-view',

            events: {
                'click .voucher-report-button': 'downloadCouponReport'
            },

            template: _.template(CouponListViewTemplate),
            linkTpl: _.template('<a href="/coupons/<%= id %>/" class="coupon-title"><%= title %></a>'),
            downloadTpl: _.template(
                '<a href="" class="btn btn-secondary btn-small voucher-report-button"' +
                ' data-coupon-id="<%= id %>"><%=gettext(\'Download Coupon Report\')%></a>'),
            url: '/api/v2/coupons/?format=datatables',

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
                        title: gettext('Custom Code'),
                        data: 'code',
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
                        title: gettext('Category'),
                        data: 'category.name',
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
            },

            renderCouponTable: function() {
                var couponTable,
                    filterPlaceholder = gettext('Search...'),
                    $emptyLabel = '<label class="sr">' + filterPlaceholder + '</label>';

                if (!$.fn.dataTable.isDataTable('#couponTable')) {
                    couponTable = this.$el.find('#couponTable').DataTable({
                        serverSide: true,
                        ajax: this.url,
                        autoWidth: false,
                        lengthMenu: [10, 25, 50, 100],
                        info: true,
                        paging: true,
                        initComplete: function() {
                            $('#couponTable_filter input').unbind()
                            .bind('keyup', function(e) {
                                // If the length is 3 or more characters, or the user pressed ENTER, search
                                if (this.value.length >= 3 || e.keyCode === 13) {
                                    couponTable.search(this.value).draw();
                                }

                                // Ensure we clear the search if they backspace far enough
                                if (this.value === '') {
                                    couponTable.search('').draw();
                                }
                            });
                        },
                        oLanguage: {
                            oPaginate: {
                                sNext: gettext('Next'),
                                sPrevious: gettext('Previous')
                            },

                            // Translators: _START_, _END_, and _TOTAL_ are placeholders. Do NOT translate them.
                            sInfo: gettext('Displaying _START_ to _END_ of _TOTAL_ coupons'),

                            // Translators: _MAX_ is a placeholder. Do NOT translate it.
                            sInfoFiltered: gettext('(filtered from _MAX_ total coupons)'),

                            // Translators: _MENU_ is a placeholder. Do NOT translate it.
                            sLengthMenu: gettext('Display _MENU_ coupons'),
                            sSearch: ''
                        },
                        order: [[0, 'asc']],
                        columns: this.getTableColumns()
                    });

                    // NOTE: #couponTable_filter is generated by dataTables
                    this.$el.find('#couponTable_filter label').prepend($emptyLabel);

                    this.$el.find('#couponTable_filter input')
                        .attr('placeholder', filterPlaceholder)
                        .addClass('field-input input-text')
                        .removeClass('form-control input-sm');
                }
            },

            render: function() {
                this.$el.html(this.template);
                this.renderCouponTable();
                return this;
            },

            /**
             * Download voucher report for a Coupon product
             */
            downloadCouponReport: function(event) {
                var couponId = $(event.currentTarget).data('coupon-id'),
                    url = '/api/v2/coupons/coupon_reports/' + couponId;

                event.preventDefault();
                window.open(url, '_blank');
                return this;
            }
        });
    }
);

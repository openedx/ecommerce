define([
        'jquery',
        'underscore',
        'backbone',
        'dataTablesBootstrap'
      ],
      function ($, _, Backbone) {

        'use strict';

        return Backbone.View.extend({

            el: '#course-list-view',

            initialize: function () {
                this.render();
            },

            render: function () {

                var filterPlaceholder = gettext('Filter by org or course ID'),
                    $emptyLabel = '<label class="sr">' + filterPlaceholder + '</label>';

                this.$el.find('#courseTable').DataTable({
                    info: false,
                    paging: false,
                    oLanguage: {
                        sSearch: ''
                    }
                });

                this.$el.find('#courseTable_filter label').prepend($emptyLabel);

                this.$el.find('#courseTable_filter input')
                    .attr('placeholder', filterPlaceholder)
                    .addClass('field-input input-text')
                    .removeClass('form-control input-sm');

                return this;
            }

        });
    }
);

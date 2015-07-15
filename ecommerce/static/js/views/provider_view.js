define([
        'jquery',
        'underscore',
        'backbone'
    ],
    function( $, _, Backbone ) {
        return Backbone.View.extend({

            initialize: function() {
                this.template = _.template($('#provider-details-tpl').text());
                this.getProviders();
                this.checkEligibility();
            },

            getProviders: function () {
                var providersIds = this.$el[0].dataset.providersIds;
                var url = lmsRootUrl + '/api/credit/v1/providers/?provider_id=' + providersIds;
                var self = this;
                $.ajax({
                    url: url,
                    method: 'GET',
                    success: function(response) {
                        if (response.length) {
                            var html = self.template(response[0]); //currently we are assuming only one provider
                            self.$el.html(html);
                            self.toggleProviderContent(true);
                        } else {
                            self.toggleProviderContent(false);
                        }
                    },
                    error: function() {
                        self.toggleProviderContent(false);
                    }
                })
            },

            checkEligibility: function () {
                var $courseDetails = $("#course-name");
                var username = $courseDetails.data("username");
                var courseKey = $courseDetails.data("course_key");
                var url = lmsRootUrl + '/api/credit/v1/eligibility/?username=' + username + '&course_key=' + courseKey;
                var self = this;
                $.ajax({
                    url: url,
                    method: 'GET',
                    success: function(response) {
                        if (response.length) {
                            var deadline = new Date(response[0]["deadline"]);
                            var formattedDate = deadline.getMonth() + "/" + deadline.getDay() + "/" + deadline.getFullYear();
                            $(".eligibility-details").find(".deadline-date").text(formattedDate);
                            self.toggleProviderContent(true);
                        } else {
                            self.toggleProviderContent(false);
                        }
                    },
                    error: function() {
                        self.toggleProviderContent(false);
                    }
                })
            },

            toggleProviderContent: function( isEnabled ) {
                // On request failure hide provider panel and show error message.
                $( '.provider-panel' ).toggleClass('hide', !isEnabled);
                $( '.error-message').toggleClass('hide', isEnabled );
            }
        });
});

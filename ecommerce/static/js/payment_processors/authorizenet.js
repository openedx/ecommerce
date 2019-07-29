(function () {
    if (!window.AuthorizeNetIFrame) window.AuthorizeNetIFrame = {};
        AuthorizeNetIFrame.onReceiveCommunication = function (querystr) {
            var params = parseQueryString(querystr);
                switch (params["action"]) {
                    case "successfulSave":
                        break;
                    case "cancel":
                        break;
                    case "resizeWindow":
                        var w = parseInt(params["width"]);
                        var h = parseInt(params["height"]);
                        var ifrm = document.getElementById("add_payment");
                        ifrm.style.width = w.toString() + "px";
                        ifrm.style.height = h.toString() + "px";
                        break;
                    case "transactResponse":
                        var ifrm = document.getElementById("add_payment");
                        ifrm.style.display = 'none';
                    }
            };

        function parseQueryString(str) {
            var vars = [];
            var arr = str.split('&');
            var pair;
            for (var i = 0; i < arr.length; i++) {
                pair = arr[i].split('=');
                vars.push(pair[0]);
                vars[pair[0]] = unescape(pair[1]);
                }
            return vars;
        }
}());


define([
    'jquery',
    'underscore.string'
], function($, _s) {
    'use strict';

    return {
        init: function(config) {
            // document.querySelector('div[aria-labelledby="card-holder-information-region"]').style.display = "none"
            this.$paymentForm = $('#paymentForm');
            this.$paymentForm.on('submit', function(event) {
                let form_data = new FormData($('#paymentForm')[0])
                $.ajax({
                    type: "POST",
                    url: config.postUrl,
                    cache: false,
                    data: form_data,
                    processData: false,
                    contentType: false,
                }).done(function ( response ) {
                    document.getElementsByName('token')[0].value = response.token
                    $("#add_payment").show();
                    $("#send_token").attr({ "action": "https://test.authorize.net/payment/payment", "target": "add_payment" }).submit();
                    $(window).scrollTop($('#add_payment').offset().top - 50);

                    // document.getElementById('send_token').submit()
                   
                }).fail(function ( data ) {
                    console.log("fail")
                });
                return false;
            });
        }
    }
});
/* Declare iFrame variable for setting in function later */
var paymentiFrame;

/* parameter definition for iFrame */
var params = {
    create: true,
    iframeId: "payment_iframe",
    settings: {
      account: "220614981961",
      parentId: "iframe",
      lang: "en",
      cvv: "required",
      inputStyle: "1",
      inputFontFamily: "font_family_1",
      expy: "single_input",
      show_placeholders: "true",
      showFrame: false,
      width: "100%",
      devServer: 'https://cert.payconex.net',
      css: {
        class_row: "margin-top: 1.5%; margin-bottom:1.5%; margin-left:1.5%; margin-right:1.5%;",
        class_input_box: "-webkit-appearance: none;-moz-appearance: none;appearance: none;display: block;outline: none;width: 99%;padding: 1%;line-height: 20px;font-size: 16px;font-weight: 300;background: #fff;border-radius: 5px;border: 1px solid #bdbdbd;",
        class_label: "display:none;",
        'class_input_box:focus': "border: 1px solid #4caf50;"
      }
    }
  }; 

/* Function to load iFrame after body loads */
function loadiFrame(){
    window.paymentiFrame = new PaymentiFrame( params );
}

/* Function to handle submission of the iFrame */
function submitPayment(post_url){
    paymentiFrame.encrypt()
    .failure( function (err) {
        //Show iframe failure response on page.
        document.getElementById('iframe-response').innerHTML = JSON.stringify(err, null, 2);
    })
    .invalidInput( function (data) {
        // Show iframe error message on page.
        error = data.invalidInputs[0]
        error_string = 'Invalid card details.\n ' + error.field + 'field: '+ error.message
        
        document.getElementById('iframe-response').innerHTML = '\
        <div class="alert alert-error">\
            <i class="icon fa fa-exclamation-triangle"></i>' + error_string + '\
        </div>'
    })
    .success( function (res) {
        //Prepare form_data with etoken (return by bluefin after encryption).
        form_data = new FormData($('#paymentForm')[0])
        form_data.append("bluefin_token", res.eToken);

        // Create PayConex request
        payConexRequest(form_data, post_url);
    })
}

//Function to POST form data to server for processing via PayConex.
function payConexRequest(data, url){
    $.ajax({
        type: "POST",
        url: url,
        cache: false,
        data: data,
        processData: false,
        contentType: false,
    }).done(function ( response ) {
        window.location.href = response.url;
    }).fail(function ( data ) {
        displayErrorMessage(gettext(
            'An error occurred while processing your payment. Please try again.'
        ));
    });
}

//Function to display error-message.
function displayErrorMessage(message) {
    $('#messages').html(
        '<div class="alert alert-error">\
            <i class="icon fa fa-exclamation-triangle"></i>'+message+
        '</div>',     
    )
}

define([
    'jquery',
    'underscore.string'
], function($, _s) {
    'use strict';

    return {
        init: function(config) {
            this.$paymentForm = $('#paymentForm');
            this.$paymentForm.on('submit', function(event) {
                submitPayment(config.postUrl);
                return false;
            });

            // replace card div with bluefin iframe
            let bluefin_iframe_code = '\
            <div class="col col-sm-12">\
                <fieldset><div id="iframe" style="overflow:hidden;"></div></fieldset>\
                <div id="iframe-response"></div>\
            </div>'

            $( bluefin_iframe_code ).insertAfter( ".pci-fields" );
            let card_div  = document.getElementsByClassName("pci-fields");
            card_div[0].style.display = "none"

            document.getElementById("card-number").required = false;
            document.getElementById("card-cvn").required = false;
            document.getElementById("card-expiry-month").required = false;
            document.getElementById("card-expiry-year").required = false;

            loadiFrame()
        }
    }
});

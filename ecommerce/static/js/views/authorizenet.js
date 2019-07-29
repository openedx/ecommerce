require([
  'jquery',
  'payment_processors/authorizenet'
], function($, AuthorizeNetProcessor) {
  'use strict';

  $(document).ready(function() {
      AuthorizeNetProcessor.init(window.AuthorizeNetConfig);
  });
});

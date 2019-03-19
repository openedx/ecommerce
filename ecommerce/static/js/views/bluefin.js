require([
  'jquery',
  'payment_processors/bluefin'
], function($, BluefinProcessor) {
  'use strict';

  $(document).ready(function() {
      BluefinProcessor.init(window.BluefinConfig);
  });
});

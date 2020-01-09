/**
 * Backbone.Route filter
 *
 * Adds support for sync/async Backbone routes filters
 *
 * @author Maksim Horbachevsky
 */

(function(factory) {
  if (typeof define === 'function' && define.amd) {
    define(['backbone', 'underscore'], factory);
  } else if (typeof exports === 'object') {
    module.exports = factory(require('backbone'), require('underscore'));
  } else {
    factory(window.Backbone, window._);
  }
})(function(Backbone, _) {

  var extend = Backbone.Router.extend;

  Backbone.Router.extend = function() {
    var child = extend.apply(this, arguments),
      childProto = child.prototype,
      parentProto = this.prototype;

    _.each(['before', 'after'], function(filter) {
      _.defaults(childProto[filter], parentProto[filter]);
    });

    return child;
  };

  _.extend(Backbone.Router.prototype, {

    /**
     * Override default route fn to call before/after filters
     *
     * @param {String} route
     * @param {String} name
     * @param {Function} [callback]
     * @return {*}
     */
    route: function(route, name, callback) {
      if (!_.isRegExp(route)) route = this._routeToRegExp(route);
      if (_.isFunction(name)) {
        callback = name;
        name = '';
      }
      if (!callback) callback = this[name];
      var router = this;
      Backbone.history.route(route, function(fragment) {
        var args = router._extractParameters(route, fragment);

        runFilters(router, router.before, fragment, args, function() {
          if (router.execute(callback, args, name) !== false) {
            router.trigger.apply(router, ['route:' + name].concat(args));
            router.trigger('route', name, args);
            Backbone.history.trigger('route', router, name, args);
            runFilters(router, router.after, fragment, args, _.identity);
          }
        });
      });
      return this;
    }
  });

  /**
   * Running all filters that matches current fragment
   *
   * @param router {Router} router instance reference
   * @param filters {Object} all available filters
   * @param fragment {String} current fragment
   * @param args {Array} fragment arguments
   * @param callback {Function}
   */
  function runFilters(router, filters, fragment, args, callback) {
    var chain = _.filter(filters, function(callback, filter) {
      filter = _.isRegExp(filter) ? filter : router._routeToRegExp(filter);
      return filter.test(fragment);
    });

    run(chain, router, fragment, args, callback);
  }

  /**
   * Recursive function to run through filters chain supporting both async calls via `next` or regular
   * return-value based chain
   *
   * @param chain {Array} filter calls chain
   * @param router {Router} router instance reference
   * @param fragment {String} current fragment
   * @param args {Array} fragment arguments
   * @param callback {Function}
   */
  function run(chain, router, fragment, args, callback) {

    // When filters chain is finished - calling `done` callback
    if (!chain.length) {
      callback.call(router);
      return;
    }

    var current = chain[0],
      tail = _.tail(chain),
      next = function() {
        run(tail, router, fragment, args, callback);
      };

    if (_.isString(current)) {
      current = router[current];
    }

    if (current.length === 3) {
      // Filter expects `next` for async - ignoring return value
      // and waiting for `next` to be called
      current.apply(router, [fragment, args, next]);
    } else {
      // Using regular filter with `false` return value that stops
      // filters execution
      if (current.apply(router, [fragment, args]) !== false) {
        next();
      }
    }
  }

});

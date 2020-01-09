describe('Backbone.Validator', function() {
  'use strict';

  var fakeLocation,
      Router,
      router,
      action,
      navigate = function(path) {
        fakeLocation.replace('http://example.com#' + path);
        Backbone.history.checkUrl();
      };

  // Fake location object
  var FakeLocation = function(href) {
    this.replace(href);
  };

  FakeLocation.prototype = {
    replace: function(href) {
      _.extend(this, _.pick($('<a></a>', {href: href})[0],
          'href',
          'hash',
          'host',
          'search',
          'fragment',
          'pathname',
          'protocol'
      ));
      // In IE, anchor.pathname does not contain a leading slash though
      // window.location.pathname does.
      if (!/^\//.test(this.pathname)) this.pathname = '/' + this.pathname;
    },

    toString: function() {
      return this.href;
    }
  };

  beforeEach(function() {
    fakeLocation = new FakeLocation('http://example.com');
    Backbone.history = _.extend(new Backbone.History(), {location: fakeLocation});
    Router = Backbone.Router.extend({
      before: {},
      after: {},
      routes: {
        'home(/user/:user/page/:page?:query)': 'home'
      },

      home: function() {
        this.isAtHome = true;
      }
    });
    router = new Router();
    Backbone.history.interval = 9;
    Backbone.history.start({pushState: false});
  });

  afterEach(function() {
    Backbone.history.stop();
  });

  describe('#before', function() {
    it('calls action if no filters', function() {
      navigate('home');
      expect(router.isAtHome).toBeTruthy();
    });

    it('calls action if all filters passed', function() {
      var spy = jasmine.createSpy('filter').and.returnValue(true);

      _.extend(router, {
        before: {
          'home': spy,
          '*any': 'onAny'
        },
        onAny: spy
      });

      navigate('home');
      expect(router.isAtHome).toBeTruthy();
      expect(spy.calls.count()).toEqual(2);
    });

    it('reject action if any filter failed', function() {
      var spy = jasmine.createSpy('filter').and.returnValue(false);

      _.extend(router, {
        before: {
          'home': spy,
          '*any': 'onAny'
        },
        onAny: spy
      });

      navigate('home');
      expect(router.isAtHome).toBeFalsy();
      expect(spy.calls.count()).toEqual(1);
    });

    it('passes params to the filter', function() {
      var spy = jasmine.createSpy('filter');

      router.before = {
        'home(/*any)': spy
      };

      navigate('home/user/sam/page/11?list=true');
      expect(spy).toHaveBeenCalledWith('home/user/sam/page/11?list=true', ['sam', '11', 'list=true', null]);
    });
  });

  describe('#after', function() {
    it('calls action if all filters passed', function() {
      var spy = jasmine.createSpy('filter').and.returnValue(true);

      _.extend(router, {
        after: {
          'home': spy,
          '*any': 'onAny'
        },
        onAny: spy
      });

      navigate('home');
      expect(router.isAtHome).toBeTruthy();
      expect(spy.calls.count()).toEqual(2);
    });

    it('calls filters unless one failed', function() {
      var spy = jasmine.createSpy('filter').and.returnValue(false);

      _.extend(router, {
        after: {
          'home': spy,
          '*any': 'onAny'
        },
        onAny: spy
      });

      navigate('home');
      expect(router.isAtHome).toBeTruthy();
      expect(spy.calls.count()).toEqual(1);
    });
  });

  describe('inheritance', function() {
    var ChildRouter, GrandChildRouter;

    beforeEach(function() {
      Router.prototype.before = {
        '*any': '_logRoute',
        'index': '_original'
      };

      Router.prototype.after = {
        '*any': '_logRoute',
        'index': '_original'
      };

      ChildRouter = Router.extend({
        before: {
          '*any-child': '_logChildRoute',
          'index': '_overridden'
        },
        after: {
          '*any-child': '_logChildRoute',
          'index': '_overridden'
        }
      });

      GrandChildRouter = ChildRouter.extend({
        before: {
          '*any-grand-child': '_logGrandChildRoute'
        },
        after: {
          '*any-grand-child': '_logGrandChildRoute'
        }
      });

      router = new GrandChildRouter();
    });

    it('inherits before filters', function() {
      expect(router.before).toEqual({
        'index': '_overridden',
        '*any': '_logRoute',
        '*any-child': '_logChildRoute',
        '*any-grand-child': '_logGrandChildRoute'
      });
    });

    it('inherits after filters', function() {
      expect(router.after).toEqual({
        'index': '_overridden',
        '*any': '_logRoute',
        '*any-child': '_logChildRoute',
        '*any-grand-child': '_logGrandChildRoute'
      });
    });
  });

  describe('async mode', function() {
    beforeEach(function() {
      jasmine.clock().install();
    });

    it('calls filters and triggers one-by-one', function() {

      var calls = [];

      router.before = {
        'home': function(fragment, args, next) {
          setTimeout(function() {
            calls.push(1);
            next();
          }, 10);
        },

        '*home': function() {
          calls.push(2);
          return true;
        },

        '*any': function(fragment, args, next) {
          setTimeout(function() {
            calls.push(3);
            next();
          }, 10);
        }
      };

      router.on('route', function() {
        calls.push(4);
      });

      router.after = {
        'home': function(fragment, args, next) {
          setTimeout(function() {
            calls.push(5);
            next();
          }, 10);
        },

        '*any': function(fragment, args, next) {
          setTimeout(function() {
            calls.push(6);
            next();
          }, 10);
        }
      };

      navigate('home');
      jasmine.clock().tick(50);

      expect(calls).toEqual([1, 2, 3, 4, 5, 6]);
    });
  });
});

Backbone Route filters v0.1.2 [![Build Status](https://travis-ci.org/fantactuka/backbone-route-filter.png?branch=master)](https://travis-ci.org/fantactuka/backbone-route-filter)
==================

Backbone Route filters allows you to have a pre-condition for the router using `before` filters and some
"after" routing calls using `after` filters. Before filters could prevent router from calling action in case 
any of them returns false. 

**Note** that `after` filters are executed only of `before` filters are passed and original route executed

Filters are inherited by extending parent's filters with child's. Child's filter have higher priority, so having same
pattern in child filters will override parent's behaviour.

Filters are also supporting async mode via calling `next` callback when filter finished. This callback should be explicitly
passed as third argument to the filter function. See `checkAuthorization` in example below.

## Installation
Using [Bower](http://twitter.github.com/bower/) `bower install backbone-route-filter` or just copy [backbone-route-filter.js](https://raw.github.com/fantactuka/backbone-route-filter/master/backbone-route-filter.js)

## Usage

```js
var Router = Backbone.Router.extend({
  routes: {
    'users': 'usersList',
    'users/:id': 'userShow',
    'account/sign-in': 'signIn'
  },

  before: {
    // Using instance methods
    'users(:/id)': 'checkAuthorization',

    // Using inline filter definition and `return false` if don't want route to be executed
    '*any': function(fragment, args) {
      var hasAccess = CurrentUser.hasAccessTo(fragment, args);
      
      if (!hasAccess) {
        Backbone.navigate('/', true);
      }
      
      return hasAccess;
    }
  },

  after: {
    // Google analytics tracking
    // After filter will be triggered only if all before filters passed and action was triggered,
    // so you'll only track pages that was displayed to user
    '*any': function(fragment) {
      goog._trackPageview(fragment);
    }
  },

  checkAuthorization: function(fragment, args, next) {
    if (this._isSignedIn) {
      // If signed in - just proceed
      next();
    } else {
      // Requesting server to check if user is authorised
      var that = this;

      $.ajax({
        url: '/auth',
        success: function() {
          that._isSignedIn = true;
          next();
        },

        error: function() {
          Backbone.navigate('login', true);
        }
      });
    }
  }
});
```

## Running tests
You can use karma runner via

```bash
npm install && grunt test
```

or directly hit html files `spec/backbone-qunit.html` and `spec/jasmine.html` to run Backbone's standard suite and
Backbone route filter specs

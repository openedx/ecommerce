// jQuery & Backbone JS Autocomplete Widget
//
// Copyright 2011 Planbox (www.planbox.com)
// Author Martin Drapeau
//
// Pass a Backbone collection and a model attribute to specify
// values for autocomplete. Apply this on an INPUT element.
// For example:
// 
//   $('input').autocomplete({
//       collection: collection,
//       attr: 'name'
//   });
//
// Constructs a UL and places it before the INPUT element.
// Will open right below, left-aligned. LI's get added the
// selected class upon hover or when the user navigates with
// the keyboard. Pressing TAB or ENTER when an item is selected
// changes the value in the INPUT. Or, if you specified a 
// callback (option onselect), will instead trigger it passing
// the selected model as argument.
//
// Options:
//   collection: The Backbone collection.
//   attr: The attribute to autocomplete on.
//   noCase: Optional. Set to true if your values are strings 
//          and you want autocomplete to be case insensitive.
//   onselect: Optional. Callback to be called when an item is
//          selected. If callback is not set, will modify the 
//          INPUT value to what has been selected.
//   scrollable_ancestor_em: Optional. If your element is inside
//          a scrollabale element, set this option to it.
//   ul_css, ul_class: Optional. Set to specify element style
//          and element class (uses jQuery's css and addClass
//          functions).
//   li_css, li_class: Optional. Set to specify element style
//          and element class (uses jQuery's css and addClass
//          functions).
//   width: Optional. Set to force a width. Otherwise will be
//          set to the width of the INPUT element.
//
// Methods:
//   show: Call to force showing the list.
//   destroy: Call to destroy and remove the widget from the
//         element.
//
// CSS: By default the UL will have class autocomplete. That
// can be overriden through option ul_class. Here is the 
// suggested styling to put in your .css file:
//    ul.autocomplete {
//    	position:absolute;
//    	background-color:white;
//    	border:1px solid #999;
//    	width:100%;
//    	font-size:12px;
//    	overflow-x:hidden;
//    	overflow-y:auto;
//    	clear:both;
//      z-index:1000;}
//    
//    ul.autocomplete li {
//    	list-style:none;
//    	cursor:pointer;
//    	padding:5px;}
//    
//    ul.autocomplete li.selected {
//    	background-color:#E1EFF9;}
//
// Note: Calling autocomplete on an element twice resets the
// widget.
//
(function($) {
	
	var defaults = {
		collection: null,
		attr: null,
		noCase: false,
		scrollable_ancestor_em: null,
		onselect: null,
		ul_class: 'autocomplete',
		ul_css: null,
		li_class: null,
		li_css: null,
		width: null,
		max_results: null
	};
	
	var methods = {
		init: function(options) {
			options || (options = {});
			
			return this.each(function(){
				var $this = $(this); // INPUT
				
				// If widget already exists - destroy it first
				if ($this.data('autocomplete')) methods.destroy.apply($this);
				
				// Turn off Browser autocomplete
				var oldAutocomplete = $this.attr('autocomplete');
				$this.attr('autocomplete', 'off');
				
				// Create
				var list_em = $('<ul>') // UL
					.addClass(options.ul_class || defaults.ul_class)
					.hide()
					.insertBefore($this);
				
				// Bind events
				$this.bind('focus.autocomplete', function(e) {
					$this.bind('blur.autocomplete', function(e) {
						$this.unbind('blur.autocomplete');
						$this.unbind('keydown.autocomplete');
						$this.unbind('keyup.autocomplete');
						list_em.hide();
						return true;
					});
					$this.bind('keydown.autocomplete', function(e) {
						return methods._inputKeydown.apply($this, [e]);
					});
					$this.bind('keyup.autocomplete', function(e) {
						return methods._inputKeyup.apply($this, [e]);
					});
				});
				
				$this.data('autocomplete', {
					target: $this,
					oldAutocomplete: oldAutocomplete,
					oldValue: null,
					list_em: list_em,
					options: $.extend({}, defaults, options)
				});
			});
		},
		// Completely removes the widget on the specified elements
		destroy: function() {
			return this.each(function(){
				var $this = $(this),
					data = $this.data('autocomplete');
				
				data.list_em.remove();
				$this.attr('autocomplete', data.oldAutocomplete);
				$this.removeData('autocomplete');
			});
		},
		show: function() {
			var $this = this;
			var data = $this.data('autocomplete');
			var options = data.options;
			var collection = options.collection;
			var attr = options.attr;
			
			var list_em = data.list_em;
			
			var str = $.trim($this.val());
			var str_lower = str.toLowerCase();
			
			// Find matches
			var result = [];
			collection.each(function(model) {
				var v = model.get(attr);
				if (v.indexOf(str) == 0 || (options.noCase && v.toLowerCase().indexOf(str_lower) == 0))
					result.push(model);
			});
			
			// Hide list if none found and return now
			if (result.length == 0) {
				list_em.hide();
				return this;
			};

			if(options.max_results && !isNaN(options.max_results)) {
				result = result.slice(0, options.max_results);
			}
			
			// We found some - position and show
			list_em.empty();
			if (!list_em.is(':visible')) {
				var pos = $this.position();
				var delta = 0;
				var scroll_em = $(options.scrollable_ancestor_em);
				if (scroll_em.length) delta = scroll_em.scrollTop();
				var x = pos.left;
				var y = pos.top+delta+$this.outerHeight(true);
				list_em.css({'left': x,'top': y});
				if (options.ul_css) list_em.css(options.ul_css);
				if (options.width) {
					list_em.width(options.width);
				} else {
					list_em.width($this.outerWidth(true)+5);
				}
				list_em.show();
			}
			
			// Build LI elements in our UL
			for (var i = 0; i < result.length; i++) {
				var model = result[i];
				var found = model.get(attr);
				var html = '<strong>'+found.substr(0, str.length)+'</strong>'+found.substr(str.length);
				var li_em = $("<li>"+html+"</li>");
				li_em.mouseover(function() {
					$(this).addClass('selected')
						.siblings('.selected').removeClass('selected');
				});
				li_em.mouseleave(function() {
					$(this).removeClass('selected');
				});
				li_em.mousedown(function() {
					var model_id = $(this).attr('model_id');
					model = collection.get(model_id);
					if (options.onselect) {
						options.onselect(model);
					} else {
						$this.val(model.get(attr));
					}
					$this.blur();
					return false;
				});
				li_em.addClass(options.li_class).attr('model_id', model.id);
				if (options.li_class) li_em.addClass(li_class);
				if (options.li_css) li_em.css(options.li_css);
				list_em.append(li_em);
			}
			
			return this;
		},
		_inputKeydown: function(e) {
			var $this = this;
			var data = $this.data('autocomplete');
			var options = data.options;
			var collection = options.collection;
			var list_em = data.list_em;
			
			// Esc
			if (e.keyCode == 27) {
				e.preventDefault();
				$this.blur();
				return false;
			}
			// Enter
			if (e.keyCode == 13 || e.keyCode == 9) {
				// If an item is selected, change input value
				var em = list_em.children('li.selected');
				if (em.length) {
					var model_id = em.attr('model_id');
					model = collection.get(model_id);
					if (options.onselect) {
						options.onselect(model);
					} else {
						this.val(model.get(options.attr));
					}
				}
				list_em.hide();
				return true;
			}
			// Down
			if (e.keyCode == 40) {
				e.preventDefault();
				var em = list_em.children('li.selected');
				if (em.length == 0) {
					list_em.children('li:first').addClass('selected');
				} else {
					if (em == list_em.children('li:last')) {
						em.removeClass('selected');
					} else {
						em.removeClass('selected').next('li').addClass('selected');
					}
				}
				return false;
			}
			// Up
			if (e.keyCode == 38) {
				e.preventDefault();
				var em = list_em.children('li.selected');
				if (em.length == 0) {
					list_em.children('li:last').addClass('selected');
				} else {
					if (em == list_em.children('li:first')) {
						em.removeClass('selected');
					} else {
						em.removeClass('selected').prev('li').addClass('selected');
					}
				}
				return false;
			}
			return true;
		},
		_inputKeyup: function(e) {
			if (e.keyCode == 27 || e.keyCode == 13 || e.keyCode == 9) return true;
			
			var $this = this;
			var data = $this.data('autocomplete');
			var list_em = data.list_em;
			
			if (data.oldValue == $this.val()) return true;
			
			data.oldValue = $this.val();
			if ($this.val().length == 0) {
				list_em.hide();
			} else {
				methods.show.apply($this);
			}
			return false;
		}
	};
	
	$.fn.autocomplete = function( method ) {
		if ( methods[method] ) {
			return methods[method].apply( this, Array.prototype.slice.call( arguments, 1 ));
		} else if ( typeof method === 'object' || ! method ) {
			return methods.init.apply( this, arguments );
		} else {
			$.error( 'Method ' +  method + ' does not exist on jQuery.autocomplete' );
		}
	};

})(jQuery);
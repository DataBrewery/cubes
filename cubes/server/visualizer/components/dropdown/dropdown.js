YUI.add('visualizer-component-dropdown', function (Y) {
  Y.namespace('Visualizer.Component');

  function DropDown(el, config) {
    this.dd = Y.one(el);
    this.MAX_OPTIONS = 10;
    this.itemClick = null;
    this.prevVal = null;
    this.val = null;
    this.width = 200;

    this.dd.addClass('dd-dropdown-container');

    var wrapper = Y.Node.create('<div>').addClass('dd-wrapper-dropdown').setStyle('width', this.width);
    this.dd.append(wrapper);
    var span = Y.Node.create('<span>');
    wrapper.append(span);
    var arrow = Y.Node.create('<div>').addClass('dd-arrow');
    wrapper.append(arrow);
    var ddDiv = Y.Node.create('<div>').addClass('dd-dropdown');
    wrapper.append(ddDiv);

    if (config) {
      if (config.maxOptions) {
        this.MAX_OPTIONS = config.maxOptions;
      }

      if (config.width) {
        this.width = config.width;
        wrapper.setStyle('width', this.width);
      }

      if (config.options) {
        this.update(config.options, false);
      }

      if (config.itemClick) this.itemClick = config.itemClick;
      if (config.val) this.val = config.val;
    }

    span.setHTML(Y.Lang.isUndefined(this.val) || Y.Lang.isNull(this.val) || this.val === '' ? '&nbsp;' : this.val);

    this.initEvents();

    return this;
  }

  DropDown.prototype = {
    initEvents : function() {
      var self = this;
   
      this.dd.one('.dd-wrapper-dropdown').on('click', function(e) {
        if (!e.target.hasClass('dd-category')) {
          Y.all('.dd-wrapper-dropdown').each(function(node) {
            if (node._yuid !== e.currentTarget._yuid) {
              node.removeClass('dd-active');
            }
          });
          this.toggleClass('dd-active');

          if (this.hasClass('dd-active')) {
            Y.one(self.dd).all('ul').removeClass('dd-hidden-list');
          }
        }

        e.stopPropagation();
      });

      this.initOptionEvents();

      Y.one('body').on('click', function(e) {
        self.dd.one('.dd-wrapper-dropdown').removeClass('dd-active');
      });
    },
    initOptionEvents: function() {
      var self = this;

      this.dd.all('ul > li.dd-nested').on('mouseover', function(e) {
        var node = e.currentTarget;

        node.one('ul').setStyle('top', node.getY() - node.ancestor('.dd-wrapper-dropdown').getY() - parseInt(node.getComputedStyle('height'), 10));
      });

      this.dd.all('ul > li:not(.dd-category)').on('click', function(e) {
        Y.one(self.dd).all('ul').addClass('dd-hidden-list');
        self.dd.all('li').removeClass('dd-selected');

        var opt = e.currentTarget;

        opt.addClass('dd-selected');
        try { opt.ancestor('.dd-nested').addClass('dd-selected'); } catch(err) {}

        self.prevVal = self.val;
        self.val = opt.getData('value');
        self.dd.one('span').setHTML(opt.getHTML());

        if (self.itemClick) {
          self.itemClick(self.val, self.prevVal);
        }
      });
    },
    getValue: function() {
      return this.val;
    },
    setValue: function(val) {
      var self = this;

      this.dd.all('li').removeClass('dd-selected');

      if (val) {
        this.dd.all('li').some(function(node) {
          if (node.getData('value') === val) {
            self.prevVal = self.val;
            self.val = val;
            self.dd.one('span').setHTML(node.getHTML());
            node.addClass('dd-selected');
            try { node.ancestor('.dd-nested').addClass('dd-selected'); } catch(err) {}
            return true;
          } else {
            return false;
          }
        });
      } else {
        this.prevVal = this.val;
        this.val = null;
        this.dd.one('span').setHTML('&nbsp;');
      }
    },
    simulateClick: function(args) {
      if (this.itemClick) {
        if (args) {
          if (!Y.Lang.isArray(args)) {
            args = [args];
          }
        }

        this.itemClick.apply(this, args ? [this.val, this.prevVal].concat(args) : [this.val, this.prevVal]);
      }
    },
    update: function(options, initEvents) {
      var valFound = false;

      var ddDiv = this.dd.one('.dd-dropdown').setStyle('width', this.width);
      ddDiv.empty();

      var ul = Y.Node.create('<ul>');
      ddDiv.append(ul);

      for (var i = 0; i < options.length; i++) {
        var opt = options[i];
        var li = Y.Node.create('<li>');
        ul.append(li);

        var val = !Y.Lang.isUndefined(opt.val) ? opt.val : opt.label;
        if (this.val === val) {
          valFound = true;
        }

        li.setHTML((!Y.Lang.isUndefined(opt.label) && !Y.Lang.isNull(opt.label)) ? opt.label : opt.val);
        li.setData('value', val);

        if (opt.category) {
          li.addClass('dd-category');
        }

        if (opt.options) {
          if (opt.options.length > this.MAX_OPTIONS) {
            li.addClass('dd-nested');
          }

          var ulNested = Y.Node.create('<ul>');
          li.append(ulNested);

          for (var k = 0; k < opt.options.length; k++) {
            var optNested = opt.options[k];
            var liNested = Y.Node.create('<li>');
            ulNested.append(liNested);

            var valNested = !Y.Lang.isUndefined(optNested.val) ? optNested.val : optNested.label;
            if (this.val === valNested) {
              valFound = true;
            }

            liNested.setHTML((!Y.Lang.isUndefined(optNested.label) && !Y.Lang.isNull(optNested.label)) ? optNested.label : optNested.val);
            liNested.setData('value', valNested);
          }
        }
      }

      if (!valFound) {
        this.prevVal = this.val;
        this.val = null;
        this.dd.one('span').setHTML('&nbsp;');
      }

      if (Y.Lang.isUndefined(initEvents) || Y.Lang.isNull(initEvents) || initEvents) {
        this.initOptionEvents();
      }
    },
    empty: function(maintainPrevVal) {
      this.dd.one('.dd-dropdown').empty();
      if (!maintainPrevVal) this.prevVal = null;
      this.val = null;
      this.dd.one('span').setHTML('&nbsp;');
    }
  };

  Y.Visualizer.Component.DropDown = DropDown;
}, '1.0', {
  requires: ['node', 'event']
});

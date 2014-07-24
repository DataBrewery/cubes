YUI.add('visualizer-nav', function (Y) {
  Y.namespace('Visualizer');

  var TIME_GROUPS = {
    'all': null,
    'year': 'year',
    'qtr': 'quarter',
    'month': 'month',
    'week': 'week',
    'day': 'day',
    'hour': 'hour',
    'min': 'minute'
  };

  var GRANULARITY_OPTIONS = {
    null: {
      def: '90D',
      options: ['2Y', '1Y', '6M', '90D', '30D', '7D', 'Custom']
    },
    'year': {
      def: '5Y',
      options: ['50Y', '20Y', '5Y', '2Y', '1Y', 'Custom']
    },
    'quarter': {
      def: '2Y',
      options: ['5Y', '2Y', '1Y', 'Custom']
    },
    'month': {
      def: '1Y',
      options: ['5Y', '2Y', '1Y', '6M', '3M', '2M', '1M', 'Custom']
    },
    'week': {
      def: '6M',
      options: ['2Y', '1Y', '6M', '12W', '8W', '4W', 'Custom']
    },
    'day': {
      def: '90D',
      options: ['1Y', '6M', '90D', '60D', '30D', '7D', 'Custom']
    },
    'hour': {
      def: '72H',
      options: ['30D', '7D', '72H', '48H', '24H', 'Custom']
    },
    'minute': {
      def: '2H',
      options: ['12H', '6H', '2H', '60MIN', '30MIN', 'Custom']
    }
  };

  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
      return v.toString(16);
    });
  }

  function getGranularityInfo(granularity) {
    var offset = parseInt(granularity, 10);
    var type = granularity.substring(granularity.indexOf(offset.toString()) + offset.toString().length).toLowerCase();

    if (type === 'y') type = 'year';
    if (type === 'q') type = 'quarter';
    if (type === 'm') type = 'month';
    if (type === 'w') type = 'week';
    if (type === 'd') type = 'day';
    if (type === 'h') type = 'hour';
    if (type === 'min') type = 'minute';

    return {
      offset: offset,
      type: type
    };
  }

  // earliest Friday today or in future
  function weekEndDate(o) {
    var d = new Date(o.getTime());
    d.setHours(0); d.setMinutes(0); d.setSeconds(0); d.setMilliseconds(0);
    var wkd = parseInt(Y.Date.format(d, {format:'%w'}), 10);
    return Y.Date.addDays(d, (wkd <= 5) ? (5-wkd) : 6);
  }

  // most recent Saturday today or in past
  function weekStartDate(o) {
    var d = new Date(o.getTime());
    d.setHours(0); d.setMinutes(0); d.setSeconds(0); d.setMilliseconds(0);
    var wkd = parseInt(Y.Date.format(d, {format: '%w'}), 10);
    return Y.Date.addDays(d,  - ((wkd < 6) ? (1+wkd) : 0));
  }

  function offsetDate(d, gran_type, drill_type, amount) {
    var orig_drill_type = drill_type;
    // safe-copy date.
    d = new Date(d.getTime());
    // always truncate to hour.
    d.setMinutes(0); d.setSeconds(0); d.setMilliseconds(0);
    // truncate according to drill_type.
    if (drill_type) {
      var tf = _date_truncators[drill_type];
      if ( !tf )
        throw "Unknown date format type: " + drill_type;
      tf(d);
    } else {
      drill_type = gran_type;
    }
    // then, offset by amount of gran_type units, translated to drill_type units, then converted to millis.
    // the above truncation effectively offsets one drill_type unit, so subtract 1.
    // for example, gran_type 'year' and drill_type 'week' means
    // truncate to the start of this week, then offset by (amount * 52 - 1).
    var offset_mult = _offset_units[gran_type][drill_type];
    var units = -(amount * offset_mult - (orig_drill_type ? 1 : 0));
    return _date_offsetters[drill_type](d, units);
  }

  var _offset_units = {
    year: { year: 1, quarter: 4, month: 12, week: 52, day: 366, hour: 366 * 24, minute: 366 * 24 * 60 },
    quarter: { quarter: 1, month: 4, week: 13, day: 92, hour: 92 * 24, minute: 92 * 24 * 60 },
    month: { month: 1, week: 5, day: 31, hour: 31 * 24, minute: 31 * 24 * 60 },
    week: { week: 1, day: 7, hour: 7 * 24, minute: 7 * 24 * 60 },
    day: { day: 1, hour: 24, minute: 24 * 60 },
    hour: { hour: 1, minute: 60 },
    minute: { minute: 1 }
  };

  var _date_truncators = {
    null: function(n) { },
    year: function(n) { n.setMonth(0); n.setDate(1); n.setHours(0); n.setMinutes(0); },
    quarter: function(n) { n.setMonth(n.getMonth() - (n.getMonth() % 3)); n.setDate(1); n.setHours(0); n.setMinutes(0); },
    month: function(n) { n.setDate(1); n.setHours(0); n.setMinutes(0); },
    day: function(n) { n.setHours(0); n.setMinutes(0); },
    date: function(n) { n.setHours(0); n.setMinutes(0); },
    hour: function(n) { n.setMinutes(0); },
    minute: function(n) { },
    week: function(n) { n.setTime( weekStartDate(n).getTime() ); }
  };

  var _date_offsetters = {
    year: Y.Date.addYears,
    quarter: function(d, a) { return Y.Date.addMonths(d, a * 3); },
    month: Y.Date.addMonths,
    day: Y.Date.addDays,
    date: Y.Date.addDays,
    week: function(d, a) { return Y.Date.addDays(d, a * 7); },
    hour: function(d, a) { return new Date(d.getTime() + (a * 3600 * 1000)); },
    minute: function(d, a) { return new Date(d.getTime() + (a * 60 * 1000)); }
  };

  var Nav = function(DataSource) {
    this.DataSource = DataSource;
    this.config = {
      datasource: null,
      layers: [],
      resultSize: null, // null -> 'all'
      timeGroup: 'day', // null -> 'all'
      granularity: '90D',
      timeFrame: {
        start: null,
        end: null
      },
      display: null, // null -> #
      annotation: null
    };
    this.activeLayerId = null;

    this.Calendars = new Y.Visualizer.Component.Calendars({
      el: '.calendar-grp',
      hidden: 'hidden'
    });

    this.Calendars.init();

    this.Display = new Y.Visualizer.Display('.content-wrapper .content', '.content-wrapper .title');

    var layer = this.addLayer();
    this._selectPage(layer.id);

    this.init();
  };

  Nav.prototype = {
    _updateLayerWidth: function() {
      var width = 0;
      Y.all('.layers .layer').each(function(node) {
        width += parseInt(node.getComputedStyle('width'), 10);
      });

      Y.one('.layers').setStyle('width', width > 0 ? width : 350);
    },

    _slideToLayer: function(id) {
      var idx = 0;
      Y.all('.layers .layer').each(function(node, i) {
        if (node.get('id') === id) {
          idx = i;
        }
      });

      Y.one('.layers').setStyle('margin-left', -350 * idx);
    },

    _updatePageArrows: function() {
      var size = Y.all('.layernav .pages .page').size();

      if (size === 1) {
        Y.one('.layernav .arrowleft').addClass('disabled');
        Y.one('.layernav .arrowright').addClass('disabled');
      } else {
        Y.one('.layernav .arrowleft').removeClass('disabled');
        Y.one('.layernav .arrowright').removeClass('disabled');

        Y.all('.layernav .pages .page').each(function(node, idx) {
          if (node.hasClass('selected') && idx === 0) {
            Y.one('.layernav .arrowleft').addClass('disabled');
          } else if (node.hasClass('selected') && idx === size - 1) {
            Y.one('.layernav .arrowright').addClass('disabled');
          }
        }, this);
      }
    },

    _addPage: function(id) {
      var node = Y.one('.layernav .pages');

      var pageNode = Y.Node.create('<div>').addClass('btn icon page');
      pageNode.setData('layer', id);
      pageNode.on('click', function(e) {
        if (e.currentTarget.hasClass('selected') || e.currentTarget.hasClass('disabled')) return;

        this._selectPage(e.currentTarget.getData('layer'));
      }, this);
      node.append(pageNode);

      if (Y.all('.layernav .pages .page').size() > 1) {
        Y.one('.layernav .delete').removeClass('disabled');
      }
    },

    _removePage: function(id) {
      Y.all('.layernav .pages .page').each(function(node) {
        if (node.getData('layer') === id) {
          node.remove();
        }
      });

      if (Y.all('.layernav .pages .page').size() <= 1) {
        Y.one('.layernav .delete').addClass('disabled');
      }
    },

    _selectPage: function(id) {
      var node = Y.one('.layernav .pages');
      node.all('.page').removeClass('selected');
      node.all('.page').each(function(page) {
        if (page.getData('layer') === id) {
          page.addClass('selected');
        }
      });

      this._updatePageArrows();

      this._slideToLayer(id);
      this.setActiveLayerId(id);
    },

    init: function() {
      // setup layer nav interaction
      Y.all('.layernav .btn.delete').on('click', function(e) {
        if (this.config.layers.length <= 1) return;

        var id = Y.one('.layernav .pages .page.selected').getData('layer');

        var doLoad = false;
        var idx = 0;
        for (var i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];

          if (layer.id === id) {
            doLoad = layer.config.cube ? true : false;
            idx = i;
            break;
          }
        }

        if (idx > 0) idx -= 1;

        this.deleteLayer(id);
        this._selectPage(this.config.layers[idx].id);

        if (doLoad) {
          this.update();
          this.load();
        }
      }, this);

      Y.all('.layernav .btn.add').on('click', function(e) {
        var layer = this.addLayer();
        this._selectPage(layer.id);
      }, this);

      Y.all('.layernav .btn.arrowleft').on('click', function(e) {
        var prevId;
        for (var i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];

          if (layer.id === this.activeLayerId) {
            if (i === 0) return;
            break;
          } else {
            prevId = layer.id;
          }
        }

        this._selectPage(prevId);
      }, this);

      Y.all('.layernav .btn.arrowright').on('click', function(e) {
        var i;
        for (i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];

          if (layer.id === this.activeLayerId) {
            if (i === this.config.layers.length - 1) return;
            break;
          }
        }

        this._selectPage(this.config.layers[i + 1].id);
      }, this);

      // setup Result Size interaction
      Y.all('.size .btn-grp .btn').on('click', function(e) {
        var node = e.currentTarget;

        if (node.hasClass('disabled') || node.hasClass('selected')) return;

        node.get('parentNode').all('.btn').removeClass('selected');
        node.addClass('selected');

        this.config.resultSize = node.getHTML().toLowerCase();
        this.load();
      }, this);

      // setup Time Group interaction
      Y.all('.group .btn-grp .btn').on('click', function(e) {
        var node = e.currentTarget;

        if (node.hasClass('disabled') || node.hasClass('selected')) return;

        node.get('parentNode').all('.btn').removeClass('selected');
        node.addClass('selected');

        var grp = node.getHTML().toLowerCase();

        for (var timeGroup in TIME_GROUPS) {
          if (timeGroup === grp) {
            this.config.timeGroup = TIME_GROUPS[timeGroup];
            break;
          }
        }

        for (var i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];

          this.updateTimeDimension(layer);
        }

        this.updateGranularity();
        this.updateTimeFrame(true);
        this.updateDisplay();
        this.load();
      }, this);

      // setup manual Filter creation
      Y.one('.filters .btn.add').on('click', function(e) {
        var node = e.currentTarget;

        if (node.hasClass('disabled')) return;

        var layer = this.getActiveLayer();

        if (!layer.config.cube) return;

        this.openFilterDialog(node);
      }, this);

      // setup Display interaction
      Y.all('.display .btn-grp .btn').on('click', function(e) {
        var node = e.currentTarget;

        if (node.hasClass('disabled') || node.hasClass('selected')) return;

        node.get('parentNode').all('.btn').removeClass('selected');
        node.addClass('selected');

        this.config.display = node.one('span').getHTML();
        this.load(true);
      }, this);

      // Footer Buttons
      var clipboard = new ZeroClipboard(Y.one('.sidebar .link').getDOMNode(), {
        moviePath: 'libs/ZeroClipboard/ZeroClipboard.swf'
      });

      clipboard.on('dataRequested', Y.bind(function(client, args) {
        var clipText;
        if (args.shiftKey) {
          clipText = window.location.origin + this.DataSource.get('lastUrl');
        } else {
          clipText = window.location.href;
        }

        clipboard.setText(clipText);

        var dialog = new Y.Visualizer.Component.Dialog({
          id: 'link-dialog',
          fields: [{
            type: 'information',
            center: true,
            value: 'Successfully copied' + (args.shiftKey ? ' Cubes Raw Data' : '') + ' URL to clipboard!'
          }],
          cancelButton: false
        });

        Y.later(2000, this, function() {
          dialog.close(true);
        });
      }, this));

      Y.one('.btn.export').on('click', function() {
        var dialog = new Y.Visualizer.Component.Dialog({
          id: 'export-dialog',
          title: 'Export',
          icon: 'images/icon-exporting-18-light.png',
          fields: [{
            type: 'information',
            value: 'Choose export type...'
          }],
          buttons: [{
            label: 'Facts',
            click: Y.bind(function() {
              dialog.close(false);
              this.exportFacts();
            }, this)
          }, {
            label: 'CSV',
            click: Y.bind(function() {
              dialog.close();
              this.exportCSV();
            }, this)
          }]
        });
      }, this);

      Y.one('.btn.save').on('click', function() {
        // TODO
      }, this);

      Y.one('.btn.reset').on('click', function() {
        this.fullReset();
      }, this);

      Y.one('.btn.logout').on('click', function() {
        Y.fire('visualizer:logout');
      }, this);

      Y.one('.fullscreen').on('click', function(e) {
        e.currentTarget.toggleClass('active');

        if (e.currentTarget.hasClass('active')) {
          Y.one('.sidebar').addClass('fullscreen');
        } else {
          Y.one('.sidebar').removeClass('fullscreen');
        }

        // wait transition time before attempting resize
        Y.later(300, this, this.resize);
      }, this);

      Y.on('visualizer:calendar_change', function(d) {
        this.config.timeFrame.start = this.Calendars.start.get('selectedDates')[0];
        this.config.timeFrame.end = this.Calendars.end.get('selectedDates')[0];

        this.updateTimeFrame();
        this.load();
      }, this);

      Y.on('visualizer:drilldown', this.drilldown, this);
      Y.on('visualizer:annotate', this.annotate, this);
    },

    getLayer: function(id) {
      for (var i = 0; i < this.config.layers.length; i++) {
        if (this.config.layers[i].id === id) {
          return this.config.layers[i];
        }
      }

      return null;
    },

    addLayer: function(config, loadCube) {
      var id = generateUUID();

      // create the UI
      var layerNode = Y.Node.create('<div>').addClass('layer').set('id', id);
      Y.one('.sidebar .layers').append(layerNode);

      var cubeNode = Y.Node.create('<div>').addClass('section cube');
      cubeNode.append(Y.Node.create('<div>').addClass('header').setHTML('Topic')); // Cube
      cubeNode.append(Y.Node.create('<div>').addClass('dropdown'));
      layerNode.append(cubeNode);

      var measureNode = Y.Node.create('<div>').addClass('section measure');
      measureNode.append(Y.Node.create('<div>').addClass('header').setHTML('View')); // Measure
      measureNode.append(Y.Node.create('<div>').addClass('dropdown'));
      layerNode.append(measureNode);

      var drilldownNode = Y.Node.create('<div>').addClass('section drilldown');
      drilldownNode.append(Y.Node.create('<div>').addClass('header').setHTML('Group By')); // Drilldown
      drilldownNode.append(Y.Node.create('<div>').addClass('dropdown'));
      layerNode.append(drilldownNode);

      // TODO: Handle filters, time dimension, in new layout
      // var filterNode = Y.Node.create('<div>').addClass('section filters');
      // filterNode.append(Y.Node.create('<div>').addClass('header pretty').setHTML('Filters'));
      // filterNode.append(Y.Node.create('<div>').addClass('filter-grp')
      //   .append(Y.Node.create('<div>').addClass('text').setHTML('N/A')));
      // layerNode.append(filterNode);

      // var timeDimensionNode = Y.Node.create('<div>').addClass('section time-dimension');
      // timeDimensionNode.append(Y.Node.create('<div>').addClass('header pretty').setHTML('Time Dimension'));
      // timeDimensionNode.append(Y.Node.create('<div>').addClass('btn-grp')
      //   .append(Y.Node.create('<div>').addClass('text').setHTML('N/A')));
      // layerNode.append(timeDimensionNode);

      this._addPage(id);
      this._updateLayerWidth();

      var baseDropdownConfig = {
        maxOptions: 20,
        width: 330
      };

      // create the config
      var layer = {
        id: id,
        config: {
          cube: null,
          measure: null,
          drilldown: null,
          filters: null,
          timeDimension: null
        },
        UI: {
          Dropdowns: {
            cube: new Y.Visualizer.Component.DropDown('#' + id + ' .cube .dropdown', Y.merge(baseDropdownConfig, {
              itemClick: Y.bind(function(id, val, prevVal, ignorePrevVal) {
                if (!ignorePrevVal && val === prevVal) return;

                var layer = this.getLayer(id);

                layer.config.cube = val;

                var continueLoad = Y.bind(function() {
                  if (val) {
                    this.populateDropdown('measure', layer);
                    this.populateDropdown('drilldown', layer);
                  } else { // clear
                    this.emptyDropdown('measure', layer);
                    this.emptyDropdown('drilldown', layer);
                  }

                  layer.config.filters = null;

                  this.update(layer);
                  this.load();
                }, this);

                if (val) {
                  this.DataSource.loadCube(val, continueLoad);
                } else {
                  continueLoad();
                }
              }, this, id)
            })),
            measure: new Y.Visualizer.Component.DropDown('#' + id + ' .measure .dropdown', Y.merge(baseDropdownConfig, {
              itemClick: Y.bind(function(id, val, prevVal, ignorePrevVal) {
                if (!ignorePrevVal && val === prevVal) return;

                var layer = this.getLayer(id);

                layer.config.measure = val;

                this.update(layer);
                this.load();
              }, this, id)
            })),
            drilldown: new Y.Visualizer.Component.DropDown('#' + id + ' .drilldown .dropdown', Y.merge(baseDropdownConfig, {
              itemClick: Y.bind(function(id, val, prevVal, ignorePrevVal) {
                if (!ignorePrevVal && val === prevVal) return;

                var layer = this.getLayer(id);

                layer.config.drilldown = val;

                this.update(layer);
                this.load();
              }, this, id)
            }))
          }
        },
        getFilterNames: function() {
          var names = [];

          if (this.config.filters) {
            for (var i = 0; i < this.config.filters.length; i++) {
              var filter = this.config.filters[i];

              if (filter.disabled || filter.invert) continue;

              for (var k = 0; k < filter.info.length; k++) {
                var info = filter.info[k];

                if (names.indexOf(info.dim) === -1) {
                  names.push(info.dim);
                }
              }
            }
          }

          return names;
        },
        addFilter: function(f) {
          if (f) {
            var filter;
            var appendFilter = false;

            if (this.config.filters) {
              for (var i = 0; i < this.config.filters.length; i++) {
                filter = this.config.filters[i];

                appendFilter = false;

                if (filter.invert || filter.disabled) {
                  appendFilter = false;
                } else if (filter.info.length < f.length) {
                  appendFilter = true;

                  for (var k = 0; k < filter.info.length; k++) {
                    var info = filter.info[k];

                    if (info.dim !== f[k].dim) {
                      appendFilter = false;
                      break;
                    }
                  }
                }

                if (appendFilter) {
                  filter.info = filter.info.concat(f.slice(f.length - 1));
                  break;
                }
              }
            }

            if (!appendFilter) {
              filter = {
                disabled: false,
                invert: false,
                info: f
              };

              if (!this.config.filters) {
                this.config.filters = [filter];
              } else {
                this.config.filters.push(filter);
              }
            }
          }
        },
        flipFilters: function() {
          if (this.config.filters) {
            for (var i = 0; i < this.config.filters.length; i++) {
              var filter = this.config.filters[i];
              filter.invert = !filter.invert;
            }
          }

          this.updateFilters(this);
        }
      };

      if (config) {
        this.updateLayer(layer, config, true);
      } else {
        this.populateDropdown('cube', layer);
      }

      this.config.layers.push(layer);

      return layer;
    },

    deleteLayer: function(id) {
      if (this.config.layers.length <= 1) return;

      for (var i = 0; i < this.config.layers.length; i++) {
        var layer = this.config.layers[i];
        if (layer.id === id) {
          this.config.layers.splice(i, 1);
          break;
        }
      }

      Y.one('.layers').one('#' + id).remove();
      this._removePage(id);
      this._updateLayerWidth();
    },

    updateLayer: function(layer, config, loadCube) {
      for (var opt in config) {
        layer.config[opt] = config[opt];

        if (opt === 'cube') {
          this.populateDropdown(opt, layer, layer.config[opt]);
        }
      }

      if (loadCube && layer.config.cube) {
        this.DataSource.loadCube(layer.config.cube, Y.bind(function() {
          this.populateDropdown('measure', layer, layer.config.measure);
          this.populateDropdown('drilldown', layer, layer.config.drilldown);

          this.updateTimeDimension(layer);
          this.updateFilters(layer);
        }, this));
      } else {
        // this.updateTimeDimension(layer);
        this.updateFilters(layer);
      }
    },

    loadCubes: function() {
      var queue = new Y.AsyncQueue();

      function loadCube(layer, isLastLayer) {
        queue.pause();

        var continueLoad = Y.bind(function() {
          this.populateDropdown('measure', layer, layer.config.measure);
          this.populateDropdown('drilldown', layer, layer.config.drilldown);

          this.updateTimeDimension(layer);
          this.updateFilters(layer);

          queue.run();

          if (isLastLayer) {
            this.update();
            this.load(false, true);
          }
        }, this);

        if (layer.config.cube) {
          this.DataSource.loadCube(layer.config.cube, continueLoad);
        } else {
          continueLoad();
        }
      }

      for (var i = 0; i < this.config.layers.length; i++) {
        var layer = this.config.layers[i];

        queue.add({
          fn: loadCube,
          context: this,
          args: [layer, i === this.config.layers.length - 1]
        });
      }

      queue.run();
    },

    resetLayer: function(id) {
      var layer = this.getLayer(id);

      layer.UI.Dropdowns.cube.setValue(null);
      layer.config.cube = null;

      this.emptyDropdown('measure', layer);
      this.emptyDropdown('drilldown', layer);
      layer.config.filters = null;

      this.updateFilters(layer);
      this.updateTimeDimension(layer);
    },

    getActiveLayer: function() {
      return this.getLayer(this.activeLayerId);
    },

    setActiveLayerId: function(id) {
      if (id) {
        this.activeLayerId = id;
      } else {
        this.activeLayerId = this.config.layers[0].id;
      }
    },

    emptyDropdown: function(id, layer) {
      var dd = layer.UI.Dropdowns[id];

      if (!dd) return;

      dd.empty();

      layer.config[id] = null;
    },

    populateDropdown: function(id, layer, val) {
      var i, firstVal, valToSet,
          valFound = false,
          options = [],
          dd = layer.UI.Dropdowns[id];

      if (!val) val = dd.getValue();

      if (!dd) return;

      if (id === 'cube' || id === 'drilldown') {
        options.push({ val: null, label: '&nbsp;' });
        firstVal = null;
      }

      if (id === 'cube') {
        items = this.DataSource.get('cubes');
      } else if (id === 'measure') {
        items = this.DataSource.getMeasures(layer.config.cube);
      }
      if (id === 'drilldown') {
        var filterNames = layer.getFilterNames();
        items = this.DataSource.getDimensions(layer.config.cube, layer.config.measure, filterNames, filterNames.length > 0);
      }

      // split data into categories
      var categoryData = {};

      for (i = 0; i < items.length; i++) {
        if (Y.Lang.isUndefined(items[i].category) || Y.Lang.isNull(items[i].category)) {
          items[i].category = 'Miscellaneous';
        }

        if (Y.Lang.isUndefined(categoryData[items[i].category]) || Y.Lang.isNull(categoryData[items[i].category])) {
          categoryData[items[i].category] = [];
        }

        categoryData[items[i].category].push(items[i]);
      }

      var sortedCategories = Y.Object.keys(categoryData).sort();

      // add options
      for (i = 0; i < sortedCategories.length; i++) {
        var cat = sortedCategories[i];

        var opts = [];
        for (var k = 0; k < categoryData[cat].length; k++) {
          opts.push({ val: categoryData[cat][k].key, label: categoryData[cat][k].label });

          if (Y.Lang.isUndefined(firstVal)) {
            firstVal = categoryData[cat][k].key;
          }

          if (!valFound && !Y.Lang.isUndefined(val) && !Y.Lang.isNull(val) && val === categoryData[cat][k].key) {
            valFound = true;
            valToSet = categoryData[cat][k].key;
          }
        }

        if (sortedCategories.length > 1) {
          options.push({ val: cat, label: cat, category: true, options: opts });
        } else {
          options = options.concat(opts);
        }
      }

      dd.update(options);

      if (valFound) {
        dd.setValue(valToSet);
      } else {
        dd.setValue(firstVal);
      }

      layer.config[id] = dd.getValue();

      return dd;
    },

    addButton: function(node, type, label, selected) {
      if (!node) return;

      var btn = Y.Node.create('<div>').addClass('btn');

      if (selected) {
        btn.addClass('selected');
      }

      if (type === 'text') {
        btn.addClass('text');
        btn.setHTML(label);
      } else {
        // TODO
      }

      node.append(btn);

      return btn;
    },

    isAtLeastOneCube: function() {
      var atLeastOneCube = false;
      for (i = 0; i < this.config.layers.length; i++) {
        var layer = this.config.layers[i];
        if (layer.config.cube) {
          atLeastOneCube = true;
          break;
        }
      }

      return atLeastOneCube;
    },

    isAtLeastOneDrilldown: function() {
      var atLeastOneDrilldown = false;
      for (i = 0; i < this.config.layers.length; i++) {
        var layer = this.config.layers[i];
        if (layer.config.drilldown) {
          atLeastOneDrilldown = true;
          break;
        }
      }

      return atLeastOneDrilldown;
    },

    update: function(layer) {
      if (layer) {
        this.updateTimeDimension(layer);
        this.updateFilters(layer);
      }

      this.updateResultSize();
      this.updateTimeGroup();
      this.updateDisplay();
    },

    updateFilters: function(layer) {
      if (!layer) return;

      var node = Y.one('.filters .filter-grp');

      node.empty();

      function emptyFilters() {
        node.append(Y.Node.create('<div>').addClass('text').setHTML('N/A'));
      }

      function removeClick(e) {
        var parentNode = e.currentTarget.get('parentNode');

        var f = JSON.stringify(parentNode.getData('filter'));
        for (var i = 0; i < layer.config.filters.length; i++) {
          var filter = layer.config.filters[i];

          if (JSON.stringify(filter) === f) {
            layer.config.filters.splice(i, 1);
            break;
          }
        }

        parentNode.remove();

        if (node.all('.filter').size() === 0) {
          emptyFilters();
        }

        this.populateDropdown('drilldown', layer);
        this.load();
      }

      function disableClick(e) {
        if (e.currentTarget.hasClass('disabled')) return;

        e.currentTarget.toggleClass('active');

        var parentNode = e.currentTarget.get('parentNode');
        if (e.currentTarget.hasClass('active')) {
          parentNode.one('.invert').removeClass('disabled');
          parentNode.one('.info').removeClass('disabled');
        } else {
          parentNode.one('.invert').addClass('disabled');
          parentNode.one('.info').addClass('disabled');
        }

        var f = JSON.stringify(parentNode.getData('filter'));
        for (var i = 0; i < layer.config.filters.length; i++) {
          var filter = layer.config.filters[i];

          if (JSON.stringify(filter) === f) {
            filter.disabled = !e.currentTarget.hasClass('active');
            break;
          }
        }

        this.populateDropdown('drilldown', layer);
        this.load();
      }

      function invertClick(e) {
        if (e.currentTarget.hasClass('disabled')) return;

        e.currentTarget.toggleClass('active');

        var parentNode = e.currentTarget.get('parentNode');
        if (e.currentTarget.hasClass('active')) {
          parentNode.one('.info').addClass('inverted');
        } else {
          parentNode.one('.info').removeClass('inverted');
        }

        var f = JSON.stringify(parentNode.getData('filter'));
        for (var i = 0; i < layer.config.filters.length; i++) {
          var filter = layer.config.filters[i];

          if (JSON.stringify(filter) === f) {
            filter.invert = e.currentTarget.hasClass('active');
            break;
          }
        }

        this.populateDropdown('drilldown', layer);
        this.load();
      }

      if (layer.config.filters && layer.config.filters.length > 0) {
        for (var i = 0; i < layer.config.filters.length; i++) {
          var filter = layer.config.filters[i];

          var filterNode = Y.Node.create('<div>').addClass('filter');
          filterNode.setData('filter', filter);
          node.append(filterNode);

          var removeNode = Y.Node.create('<div>').addClass('btn icon remove');
          removeNode.on('click', removeClick, this);
          filterNode.append(removeNode);

          var disabledNode = Y.Node.create('<div>').addClass('checkbox');
          disabledNode.on('click', disableClick, this);
          filterNode.append(disabledNode);

          var invertNode = Y.Node.create('<div>').addClass('text invert');
          invertNode.on('click', invertClick, this);
          filterNode.append(invertNode);

          var infoNode = Y.Node.create('<div>').addClass('info');
          filterNode.append(infoNode);

          if (filter.disabled) {
            invertNode.addClass('disabled');
            infoNode.addClass('disabled');
          } else {
            disabledNode.addClass('active');
          }

          if (filter.invert) {
            invertNode.addClass('active');
            infoNode.addClass('inverted');
          }

          for (var k = 0; k < filter.info.length; k++) {
            var info = filter.info[k];

            if (k > 0) {
              infoNode.append(Y.Node.create('<span>').addClass('text').setHTML(':'));
            }

            infoNode.append(Y.Node.create('<span>').addClass('text').setHTML(this.DataSource.getDisplayName(layer.config.cube, info.dim)));
            infoNode.append(Y.Node.create('<span>').addClass('text').setHTML('='));
            infoNode.append(Y.Node.create('<span>').addClass('text').setHTML(info.label || info.val));
          }
        }
      } else {
        emptyFilters();
      }
    },

    updateTimeDimension: function(layer) {
      if (!layer) return;

      var node = Y.one('.time-dimension .btn-grp');

      var selected;
      try {
        selected = node.one('.selected').getData('val');
      } catch(e) {}

      node.empty();

      function emptyTimeDimension() {
        node.append(Y.Node.create('<div>').addClass('text').setHTML('N/A'));
        layer.config.timeDimension = null;
      }

      function btnClick(e) {
        var btnNode = e.currentTarget;

        if (btnNode.hasClass('disabled') || btnNode.hasClass('selected')) return;

        btnNode.get('parentNode').all('.btn').removeClass('selected');
        btnNode.addClass('selected');

        layer.config.timeDimension = btnNode.getData('val');

        this.updateTimeGroup();
        this.updateDisplay();
        this.load();
      }

      if (!layer.config.cube) {
        emptyTimeDimension();
      } else {
        var btns = [];
        var dims = this.DataSource.getDateDimensionsInfo(layer.config.cube);

        if (dims) {
          for (var i = 0; i < dims.length; i++) {
            var btn = this.addButton(node, 'text', dims[i].label, selected === dims[i].val || layer.config.timeDimension === dims[i].val);
            btn.setData('val', dims[i].val);
            btn.on('click', btnClick, this);

            btns.push(btn);
          }
        }

        if (btns.length === 0) {
          emptyTimeDimension();
        } else if (!node.one('.selected')) {
          btns[0].addClass('selected');
          layer.config.timeDimension = node.one('.selected').getData('val');
        }
      }
    },

    updateResultSize: function() {
      var node = Y.one('.size .btn-grp');

      var disabledSizes = [];
      for (var i = 0; i < this.config.layers.length; i++) {
        var layer = this.config.layers[i];

        if (layer.config.drilldown && this.DataSource.isHighCardinality(layer.config.cube, layer.config.drilldown, null, layer.getFilterNames())) {
          disabledSizes.push('all');
          break;
        }
      }

      var atLeastOneDrilldown = this.isAtLeastOneDrilldown();
      if (!atLeastOneDrilldown) {
        disabledSizes.push('top', 'bottom');
      }

      var atLeastOneCube = this.isAtLeastOneCube();

      node.all('.btn').each(function(btn) {
        var resultSize = btn.getHTML().toLowerCase();

        if (this.config.resultSize === resultSize) {
          btn.addClass('selected');
        }

        if (disabledSizes.indexOf(resultSize) !== -1 || !atLeastOneCube) {
          btn.addClass('disabled');
        } else {
          btn.removeClass('disabled');
        }
      }, this);

      var selected = node.one('.selected');
      if (!selected || selected.hasClass('disabled')) {
        try { selected.removeClass('selected'); } catch(e) {}
        try { node.one('.btn:not(.disabled)').addClass('selected'); } catch(e) {}
      }

      this.config.resultSize = node.one('.selected') ? node.one('.selected').getHTML().toLowerCase() : null;
    },

    updateTimeGroup: function() {
      var node = Y.one('.group .btn-grp');

      var atLeastOneCube = this.isAtLeastOneCube();

      node.all('.btn').each(function(btn) {
        var grp = TIME_GROUPS[btn.getHTML().toLowerCase()];

        if (!atLeastOneCube) {
          btn.addClass('disabled');
          return;
        }

        if (this.config.timeGroup === grp) {
          btn.addClass('selected');
        } else {
          btn.removeClass('selected');
        }

        if (grp === null) {
          btn.removeClass('disabled');
          return;
        }

        for (var i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];

          if (this.DataSource.isValidTimeframe(layer.config.cube, grp, layer.config.timeDimension)) {
            btn.removeClass('disabled');
          } else {
            btn.addClass('disabled');
            return;
          }
        }
      }, this);

      var selected = node.one('.selected');
      if (!selected || selected.hasClass('disabled')) {
        try { selected.removeClass('selected'); } catch(e) {}
        try { node.one('.btn:not(.disabled)').addClass('selected'); } catch(e) {}
      }

      this.config.timeGroup = node.one('.selected') ? TIME_GROUPS[node.one('.selected').getHTML().toLowerCase()] : null;

      this.updateGranularity();
    },

    updateGranularity: function() {
      var i;
      var node = Y.one('.granularity .btn-grp');

      var selected = node.one('.selected') ? node.one('.selected').getHTML() : null;

      node.empty();

      var gran = GRANULARITY_OPTIONS[this.config.timeGroup];

      function btnClick(e) {
        var btnNode = e.currentTarget;
        var gran = btnNode.getHTML().toLowerCase();

        if (gran !== 'custom' && (btnNode.hasClass('disabled') || btnNode.hasClass('selected'))) return;

        btnNode.get('parentNode').all('.btn').removeClass('selected');
        btnNode.addClass('selected');

        this.config.granularity = gran;

        if (gran === 'custom') {
          var range = this.DataSource.getDateRange(this.getActiveLayer().config.cube);
          this.Calendars.toggleVisibility(null, btnNode, this.config.timeGroup, this.config.timeFrame, range[0], range[1]);
          this.updateTimeFrame(true);
        } else {
          this.updateTimeFrame();
          this.load();
        }
      }

      var atLeastOneCube = this.isAtLeastOneCube();

      var btns = [];
      for (i = 0; i < gran.options.length; i++) {
        var opt = gran.options[i];

        var btn = this.addButton(node, 'text', opt, this.config.granularity === opt.toLowerCase());
        if (opt.toLowerCase() === 'custom') btn.addClass('calendar-btn');
        btn.on('click', btnClick, this);

        if (!atLeastOneCube) {
          btn.addClass('disabled');
        } else if (opt.toLowerCase() !== 'custom') {
          var granInfo = getGranularityInfo(opt);
          var dateRange = this.DataSource.getDateRange(this.getActiveLayer().config.cube);
          var startDate = offsetDate(dateRange[1], granInfo.type, this.config.timeGroup, granInfo.offset);

          if (startDate < dateRange[0]) {
            btn.addClass('disabled');
          }
        }

        btns.push(btn);
      }

      if (!node.one('.selected')) {
        node.all('.btn').each(function(btn) {
          if (btn.getHTML() === gran.def) {
            btn.addClass('selected');
          }
        }, this);
      }

      selected = node.one('.selected');
      if (!selected || selected.hasClass('disabled')) {
        try { selected.removeClass('selected'); } catch(e) {}
        try { node.one('.btn:not(.disabled)').addClass('selected'); } catch(e) {}
      }

      this.config.granularity = node.one('.selected') ? node.one('.selected').getHTML().toLowerCase() : null;
      this.updateTimeFrame();
    },

    updateTimeFrame: function(constrainCustom) {
      var node = Y.one('.timeframe');

      if (this.config.granularity === 'custom') {
        if (constrainCustom) {
          this.Calendars.constrainDates(this.config.timeGroup);
          this.config.timeFrame.start = this.Calendars.start.get('selectedDates')[0];
          this.config.timeFrame.end = this.Calendars.end.get('selectedDates')[0];
        }
      } else if (this.config.granularity) {
        var granInfo = getGranularityInfo(this.config.granularity);
        var endDate = this.DataSource.getDateRange(this.getActiveLayer().config.cube)[1];
        var startDate = offsetDate(endDate, granInfo.type, this.config.timeGroup, granInfo.offset);
        this.config.timeFrame.start = startDate;
        this.config.timeFrame.end = endDate;
      } else {
        this.config.timeFrame.start = null;
        this.config.timeFrame.end = null;
      }

      node.one('.start').setHTML(this.config.timeFrame.start ? Y.Date.format(this.config.timeFrame.start, { format: '%b %d, %Y' }) : 'N/A');
      node.one('.end').setHTML(this.config.timeFrame.end ? Y.Date.format(this.config.timeFrame.end, { format: '%b %d, %Y' }) : 'N/A');
    },

    updateDisplay: function() {
      var node = Y.one('.display .btn-grp');

      var atLeastOneCube = false,
          atLeastOnePercentageMeasure = false,
          atLeastOneDrilldown = false,
          atLeastOneFullyNonadditive = false;
      for (var i = 0; i < this.config.layers.length; i++) {
        var layer = this.config.layers[i];

        if (layer.config.cube) {
          atLeastOneCube = true;
        }

        if (this.DataSource.getMeasurementType(layer.config.cube, layer.config.measure) === 'percent') {
          atLeastOnePercentageMeasure = true;
        }

        if (layer.config.drilldown) {
          atLeastOneDrilldown = true;
        }

        if (this.DataSource.isFullyNonadditive(layer.config.cube, layer.config.measure, layer.config.drilldown)) {
          atLeastOneFullyNonadditive = true;
        }
      }

      var disabledDisplays = [];

      if (!atLeastOneCube) {
        if (disabledDisplays.indexOf('text') === -1) disabledDisplays.push('text');
        if (disabledDisplays.indexOf('table') === -1) disabledDisplays.push('table');
      }

      if (atLeastOnePercentageMeasure || atLeastOneFullyNonadditive) {
        if (disabledDisplays.indexOf('pie') === -1) disabledDisplays.push('pie');
        if (disabledDisplays.indexOf('donut') === -1) disabledDisplays.push('donut');
        if (disabledDisplays.indexOf('stacked') === -1) disabledDisplays.push('stacked');
        if (disabledDisplays.indexOf('expanded') === -1) disabledDisplays.push('expanded');
        if (disabledDisplays.indexOf('stream') === -1) disabledDisplays.push('stream');
      }

      if (!atLeastOneDrilldown) {
        if (disabledDisplays.indexOf('bar') === -1) disabledDisplays.push('bar');
        if (disabledDisplays.indexOf('pie') === -1) disabledDisplays.push('pie');
        if (disabledDisplays.indexOf('donut') === -1) disabledDisplays.push('donut');
        if (disabledDisplays.indexOf('expanded') === -1) disabledDisplays.push('expanded');
      } else {
        if (disabledDisplays.indexOf('text') === -1) disabledDisplays.push('text');
      }

      if (!this.config.timeGroup) {
        if (disabledDisplays.indexOf('line') === -1) disabledDisplays.push('line');
        if (disabledDisplays.indexOf('index') === -1) disabledDisplays.push('index');
        if (disabledDisplays.indexOf('stacked') === -1) disabledDisplays.push('stacked');
        if (disabledDisplays.indexOf('expanded') === -1) disabledDisplays.push('expanded');
        if (disabledDisplays.indexOf('stream') === -1) disabledDisplays.push('stream');
        if (disabledDisplays.indexOf('heatmap') === -1) disabledDisplays.push('heatmap');
      } else {
        if (disabledDisplays.indexOf('text') === -1) disabledDisplays.push('text');
        if (disabledDisplays.indexOf('bar') === -1) disabledDisplays.push('bar');
        if (disabledDisplays.indexOf('pie') === -1) disabledDisplays.push('pie');
        if (disabledDisplays.indexOf('donut') === -1) disabledDisplays.push('donut');
      }

      if (!this.config.timeGroup && !atLeastOneDrilldown) {
        if (disabledDisplays.indexOf('table') === -1) disabledDisplays.push('table');
      }

      node.all('.btn').each(function(btn) {
        var type = btn.one('span').getHTML();

        if (type === this.config.display) {
          btn.addClass('selected');
        }

        if (disabledDisplays.indexOf(type) !== -1) {
          btn.addClass('disabled');
        } else {
          btn.removeClass('disabled');
        }
      }, this);

      var selected = node.one('.selected');
      if (!selected || selected.hasClass('disabled')) {
        try { selected.removeClass('selected'); } catch(e) {}
        try { node.one('.btn:not(.disabled)').addClass('selected'); } catch(e) {}
      }

      this.config.display = node.one('.selected span') ? node.one('.selected span').getHTML() : null;
    },

    drilldown: function(d) {
      var layer = this.getActiveLayer();

      if (!d || !layer || !layer.config.drilldown) return;

      var data = d.data.raw ? d.data.raw : d.data;
      var key;

      if (layer.config.drilldown === this.DataSource.getSplitDimensionString()) {
        var withinSplit;

        for (key in data) {
          if (key === layer.config.drilldown) {
            withinSplit = data[key];
          }
        }

        if (!Y.Lang.isUndefined(withinSplit) && !Y.Lang.isNull(withinSplit)) {
          if (!withinSplit && layer.config.filters) {
            layer.config.flipFilters();
          }
        }

        this.populateDropdown('drilldown', layer);
        layer.UI.Dropdowns.drilldown.setValue(null);
        layer.UI.Dropdowns.drilldown.simulateClick(true);
      } else {
        var drillLevelInfo = this.DataSource.getDrillLevelInfo(layer.config.cube, layer.config.drilldown);

        if (drillLevelInfo) {
          var info = [];
          for (var i = 0; i < drillLevelInfo.levels.length; i++) {
            var level = drillLevelInfo.levels[i];

            var levelKey = level.key ? level.key : (level.name ? level.name : level.dim);
            for (key in data) {
              if (key.replace(':', '.') === levelKey.replace(':', '.')) { //(level.name ? level.name.replace(':', '.') : level.dim.replace(':', '.'))) {
                info.push({
                  dim: level.name ? level.name : level.dim,
                  val: data[key] === null ? this.DataSource.getNullString() : data[key],
                  label: level.labelKey ? (level.key === level.labelKey ? null : (data[level.labelKey] === null ? this.DataSource.getNullString() : data[level.labelKey])) : null
                });
              }
            }
          }

          if (info.length > 0) {
            layer.addFilter(info);

            this.populateDropdown('drilldown', layer);
            layer.UI.Dropdowns.drilldown.setValue(!drillLevelInfo.isLastLevel ? drillLevelInfo.nextLevel : null);
            layer.UI.Dropdowns.drilldown.simulateClick(true);
          }
        }
      }
    },

    annotate: function(cfg) {
      if (Y.Lang.isUndefined(cfg)) cfg = null;

      if (cfg && cfg.bbox) {
        cfg.bbox[0] = new Date(cfg.bbox[0]).getTime();
        cfg.bbox[2] = new Date(cfg.bbox[2]).getTime();
      }

      this.config.annotation = Y.Lang.isUndefined(cfg) ? null : cfg;

      Y.fire('visualizer:annotate:update');
    },

    openFilterDialog: function(node) {
      var layer = this.getActiveLayer();
      var filterNames = layer.getFilterNames();

      var dialog;
      var filterInfo = [];

      var oldDialog = Y.one('#create-filter-dialog');
      if (oldDialog) {
        oldDialog.remove(true);
      }

      function updateInfo(g, v, l) {
        var found = false;
        for (var i = 0; i < filterInfo.length; i++) {
          if (filterInfo[i].dim === g) {
            filterInfo[i].val = v;
            filterInfo[i].label = l;
            found = true;
            break;
          }
        }

        if (!found) {
          filterInfo.push({
            dim: g,
            val: v,
            label: l
          });
        }
      }

      function removeInfo(g) {
        for (var i = 0; i < filterInfo.length; i++) {
          if (filterInfo[i].dim === g) {
            filterInfo = filterInfo.slice(0, i);
            break;
          }
        }
      }

      function getGroupNames() {
        var groupNames = [];
        for (var i = 0; i < filterInfo.length; i++) {
          groupNames.push(filterInfo[i].dim);
        }

        return groupNames;
      }

      function mergeFilters(filters, f, parentDims, returnFilterInfo) {
        filters = Y.clone(filters);

        var filter;
        var appendFilter = false;

        if (filters) {
          for (var i = 0; i < filters.length; i++) {
            filter = filters[i];

            appendFilter = false;

            if (!filter.invert && !filter.disabled) {
              appendFilter = true;

              for (var k = 0; k < filter.info.length; k++) {
                var info = filter.info[k];

                if (parentDims.indexOf(info.dim) === -1) {
                  appendFilter = false;
                  break;
                }
              }
            }

            if (appendFilter) {
              filter.info = filter.info.concat(f);
              if (returnFilterInfo) return filter.info;
              break;
            }
          }
        }

        if (!appendFilter) {
          filter = {
            disabled: false,
            invert: false,
            info: f
          };

          if (!filters) {
            filters = [filter];
          } else {
            filters.push(filter);
          }

          if (returnFilterInfo) return f;
        }

        return filters;
      }

      var buildFilterGroup = Y.bind(function(idx, nextLevel) {
        if (!idx) idx = 0;

        var groupItems = [];
        if (idx === 0) {
          var items = this.DataSource.getDimensions(layer.config.cube, layer.config.measure, filterNames.concat(getGroupNames()));

          for (var i = 0; i < items.length; i++) {
            if (!items[i].topLevel) continue;

            groupItems.push({
              value: items[i].key,
              label: items[i].label
            });
          }
        } else {
          groupItems.push({
            value: nextLevel,
            label: this.DataSource.getDisplayName(layer.config.cube, nextLevel)
          });
        }

        var field = {
          id: 'filter-grp_' + idx,
          type: 'dropdown',
          width: 200,
          label: 'Filter By',
          values: groupItems,
          on: {
            change: Y.bind(function(grp, grpLabel, prevGrp) {
              dialog.removeFields('filter-grp_' + idx, 'after');
              if (prevGrp) removeInfo(prevGrp);

              if (!grp) return;

              var highCardinality = this.DataSource.isHighCardinality(layer.config.cube, grp, null, filterNames.concat(getGroupNames()));
              var drillLevelInfo = this.DataSource.getDrillLevelInfo(layer.config.cube, grp);

              if (!highCardinality) {
                dialog.setLoadingState(true);

                var parentDims = [];
                if (drillLevelInfo) {
                  for (var i = 0; i < drillLevelInfo.levels.length - 1; i++) {
                    parentDims.push(drillLevelInfo.levels[i].key.replace('.', ':'));
                  }
                }
                var mergedFilters = mergeFilters(layer.config.filters, filterInfo, parentDims);

                this.DataSource.queryMembers(layer.config.cube, grp, mergedFilters, Y.bind(function(data) {
                  data = data.data;

                  var drillInfo = this.DataSource.getDrillInfo(layer.config.cube, grp);

                  var items = [];
                  var sortNumbers = true;
                  var duplicateLabelMap = {};
                  var i;
                  for (i = 0; i < data.length; i++) {
                    var valueKey = drillInfo.keys[drillInfo.keys.length - 1];
                    var key = data[i][valueKey];
                    var label = data[i][drillInfo.labels[drillInfo.labels.length - 1]];

                    if (typeof label !== 'number') {
                      sortNumbers = false;
                    }

                    items.push({
                      value: key,
                      valueKey: valueKey,
                      label: label,
                      trueLabel: label
                    });
                  }

                  for (i = 0; i < items.length; i++) {
                    var found = false;
                    for (k = i + 1; k < items.length; k++) {
                      if (items[k].label === items[i].label) {
                        found = true;
                        items[k].label = items[k].label + ' (' + items[k].valueKey + ': ' + items[k].value + ')';
                        duplicateLabelMap[items[k].label] = items[k].trueLabel;
                      }
                    }
                    if (found) {
                      items[i].label = items[i].label + ' (' + items[i].valueKey + ': ' + items[i].value + ')';
                      duplicateLabelMap[items[i].label] = items[i].trueLabel;
                    }
                  }

                  if (sortNumbers) {
                    items.sort(function(a, b) {
                      return a.label - b.label;
                    });
                  } else {
                    items.sort(function(a, b) {
                      if ((a.label ? a.label.toLowerCase() : '') < (b.label ? b.label.toLowerCase() : '')) return -1;
                      if ((a.label ? a.label.toLowerCase() : '') > (b.label ? b.label.toLowerCase() : '')) return 1;
                      return 0;
                    });
                  }

                  updateInfo(grp, items[0].value, items[0].trueLabel);

                  var field = {
                    id: 'filter-value_' + idx,
                    type: 'dropdown',
                    width: 200,
                    allowEmpty: false,
                    label: 'Value',
                    values: items,
                    on: {
                      change: function(val, valLabel) {
                        removeInfo(grp);
                        updateInfo(grp, val, duplicateLabelMap[valLabel] ? duplicateLabelMap[valLabel] : valLabel);

                        var nextGrpField = dialog.getField('filter-grp_' + (idx + 1));
                        if (nextGrpField) {
                          dialog.updateFieldValue('filter-grp_' + (idx + 1), null);
                          dialog.removeFields('filter-grp_' + (idx + 1), 'after');
                        }
                      }
                    }
                  };

                  if (dialog.getField('filter-value_' + idx)) {
                    dialog.replaceField('filter-value_' + idx, field);
                  } else {
                    dialog.addField(field, 'filter-grp_' + idx, 'after');
                  }

                  if (drillLevelInfo && drillLevelInfo.nextLevel && !drillLevelInfo.isLastLevel) {
                    dialog.addField(buildFilterGroup(idx + 1, drillLevelInfo.nextLevel));
                  }

                  dialog.setLoadingState(false);
                }, this), function() {
                  // TODO: Handle failure
                  dialog.setLoadingState(false);
                });
              } else { // high cardinality
                var field = {
                  id: 'filter-value_' + idx,
                  type: 'text',
                  width: 200,
                  label: 'Value',
                  on: {
                    change: function(val) {
                      removeInfo(grp);
                      updateInfo(grp, val);

                      var nextGrpField = dialog.getField('filter-grp_' + (idx + 1));
                      if (nextGrpField) {
                        dialog.updateFieldValue('filter-grp_' + (idx + 1), null);
                        dialog.removeFields('filter-grp_' + (idx + 1), 'after');
                      }
                    }
                  }
                };

                if (dialog.getField('filter-value_' + idx)) {
                  dialog.replaceField('filter-value_' + idx, field);
                } else {
                  dialog.addField(field, 'filter-grp_' + idx, 'after');
                }

                if (drillLevelInfo && drillLevelInfo.nextLevel && !drillLevelInfo.isLastLevel) {
                  dialog.addField(buildFilterGroup(idx + 1, drillLevelInfo.nextLevel));
                }
              }
            }, this)
          }
        };

        return [field];
      }, this);

      dialog = new Y.Visualizer.Component.Dialog({
        id: 'create-filter-dialog',
        parent: node.get('parentNode').get('parentNode'),
        modal: false,
        flyout: 'right',
        fields: [
          buildFilterGroup()
        ],
        buttons: [{
          label: 'Create',
          click: Y.bind(function() {
            var i;

            if (filterInfo && filterInfo.length > 0) {
              // fix for hierarchy dimensions
              for (i = 0; i < filterInfo.length; i++) {
                var dim = filterInfo[i].dim;
                if (dim.indexOf('@') !== -1) {
                  if (dim.indexOf(':') !== -1) {
                    filterInfo[i].dim = dim.replace(dim.substring(dim.indexOf('@'), dim.indexOf(':')), '');
                  } else {
                    filterInfo[i].dim = dim.substring(0, dim.indexOf('@'));
                  }
                }
              }

              var drillLevelInfo = this.DataSource.getDrillLevelInfo(layer.config.cube, filterInfo[filterInfo.length - 1].dim);

              var parentDims = [];
              if (drillLevelInfo) {
                for (i = 0; i < drillLevelInfo.levels.length - 1; i++) {
                  parentDims.push(drillLevelInfo.levels[i].key.replace('.', ':'));
                }
              }
              var mergedFilterInfo = mergeFilters(layer.config.filters, filterInfo, parentDims, true);

              layer.addFilter(mergedFilterInfo);

              this.populateDropdown('drilldown', layer);
              layer.UI.Dropdowns.drilldown.setValue(drillLevelInfo && drillLevelInfo.nextLevel && !drillLevelInfo.isLastLevel ? drillLevelInfo.nextLevel : null);
              layer.UI.Dropdowns.drilldown.simulateClick(true);
            }

            dialog.close();
          }, this)
        }]
      });
    },

    exportFacts: function() {
      var layer = this.getActiveLayer();

      if (!layer || !layer.config.cube) return;

      var i;
      var fields = this.DataSource.getFields(layer.config.cube);

      var cols = {};

      for (i = 0; i < fields.length; i++) {
        var checked;

        if (fields[i].type === 'measure') {
          checked = true;
        } else if (layer.config.drilldown) {
          if ((fields[i].type === 'dimension' || fields[i].type === 'level') && (layer.config.drilldown.replace(':', '.') === fields[i].key.replace(':', '.')) ||
            (fields[i].type === 'attribute' && layer.config.drilldown.replace(':', '.') === fields[i].parent.replace(':', '.')))
          {
            checked = true;
          } else {
            checked = false;
          }
        } else {
          checked = false;
        }

        var cbValue = {
          checked: checked,
          value: fields[i].key,
          label: fields[i].label
        };

        if (fields[i].type === 'detail') {
          if (cols['details']) {
            cols['details'].values.push(cbValue);
          } else {
            cols['details'] = {
              id: 'details-cb-grp',
              type: 'checkbox-group',
              inline: false,
              styles: { verticalAlign: 'top' },
              label: 'Details',
              sortIndex: 0,
              values: [cbValue]
            };
          }
        } else if (fields[i].type === 'measure') {
          if (cols['measures']) {
            cols['measures'].values.push(cbValue);
          } else {
            cols['measures'] = {
              id: 'measures-cb-grp',
              type: 'checkbox-group',
              inline: false,
              styles: { verticalAlign: 'top' },
              label: 'Measures',
              sortIndex: 1,
              values: [cbValue]
            };
          }
        } else if (fields[i].type === 'date') {
          if (cols['dates']) {
            cols['dates'].values.push(cbValue);
          } else {
            cols['dates'] = {
              id: 'dates-cb-grp',
              type: 'checkbox-group',
              inline: false,
              styles: { verticalAlign: 'top' },
              label: 'Dates',
              sortIndex: 2,
              values: [cbValue]
            };
          }
        } else {
          if (cols['dimensions']) {
            cols['dimensions'].values.push(cbValue);
          } else {
            cols['dimensions'] = {
              id: 'dimensions-cb-grp',
              type: 'checkbox-group',
              inline: false,
              styles: { verticalAlign: 'top' },
              label: 'Dimensions',
              sortIndex: 3,
              values: [cbValue]
            };
          }
        }
      }

      var col;

      function valSort(a, b) {
        if (a.label.toLowerCase() < b.label.toLowerCase()) return -1;
        if (a.label.toLowerCase() > b.label.toLowerCase()) return 1;
        return 0;
      }

      for (col in cols) {
        cols[col].values.sort(valSort);
      }

      var dialogColumns = [];
      for (col in cols) {
        dialogColumns.push(cols[col]);
      }

      dialogColumns.sort(function(a, b) {
        return a.sortIndex - b.sortIndex;
      });

      var dialog = new Y.Visualizer.Component.Dialog({
        id: 'export-facts-dialog',
        title: 'Facts Export',
        icon: 'images/icon-exporting-18-light.png',
        description: 'Export Facts for ' + this.DataSource.getDisplayName(layer.config.cube) + ' into CSV format.',
        fields: [dialogColumns],
        buttons: [{
          label: 'Export',
          inverted: true,
          click: Y.bind(function() {
            function getCheckedFields(id) {
              var checkedFields = [];

              var cbNode = dialog.getField(id);
              if (cbNode) {
                cbNode.all('input').each(function(n) {
                  if (n.get('checked')) {
                    checkedFields.push(n.get('value'));
                  }
                });
              }

              return checkedFields;
            }

            var fields = [];
            fields = fields.concat(getCheckedFields('details-cb-grp'));
            fields = fields.concat(getCheckedFields('measures-cb-grp'));
            fields = fields.concat(getCheckedFields('dates-cb-grp'));
            fields = fields.concat(getCheckedFields('dimensions-cb-grp'));

            if (fields.length > 0) {
              this.DataSource.exportFacts(this.config, layer.config, fields, 'csv');
              dialog.close();
            } else {
              var errorExportDialog = new Y.Visualizer.Component.Dialog({
                id: 'error-export-dialog',
                parent: 'export-facts-dialog',
                icon: 'images/warning-icon-color.png',
                title: 'Export Failed',
                fields: [{
                  type: 'information',
                  center: true,
                  value: 'No fields are selected!'
                }]
              });
            }
          }, this)
        }]
      });
    },

    exportCSV: function() {
      this.DataSource.exportData(this.config, this.getActiveLayer().config, 'csv');
    },

    load: function(ignoreLoad, ignoreURLUpdate) {
      if (!this.config.display) {
        ignoreLoad = true;
      }

      if (!ignoreURLUpdate) {
        this.config.annotation = null;
      }

      Y.fire('visualizer:nav_change', ignoreLoad, ignoreURLUpdate);
    },

    render: function(data, ignoreLoad) {
      if (!ignoreLoad && (!data || (Y.Lang.isArray(data) && data.length === 0))) {
        Y.fire('visualizer:empty_data');
        return;
      }

      if (!this.config.display) {
        this.Display.clear();
      } else {
        this.Display.render(data, this.generateSimpleConfig(), this.DataSource);

        if (this.config.display === 'table') {
          var exportNode = Y.Node.create('<div>').addClass('viz-table-export');
          exportNode.setAttribute('title', 'Export to CSV');
          exportNode.on('click', function() {
            this.exportCSV();
          }, this);

          Y.one('.viz-table').append(exportNode);
        }
      }
    },

    generateSimpleConfig: function() {
      var config = {};

      for (var opt in this.config) {
        if (opt === 'layers') {
          config[opt] = [];

          for (var i = 0; i < this.config.layers.length; i++) {
            var layer = this.config.layers[i];

            config[opt].push(Y.merge({}, layer.config));
          }
        } else {
          config[opt] = this.config[opt];
        }
      }

      return config;
    },

    build: function(config) {
      var updateFirst = true;

      this.reset();

      if (config) {
        for (var opt in config) {
          if (opt !== 'layers') {
            if (opt === 'timeFrame') {
              for (var tfOpt in config[opt]) {
                config[opt][tfOpt] = Y.Date.parse(config[opt][tfOpt]);
              }
              this.Calendars.updateDates(config[opt]);
            }

            this.config[opt] = config[opt];
          }
        }

        if (config.layers) {
          for (var i = 0; i < config.layers.length; i++) {
            var layerConfig = config.layers[i];

            if (i === 0 && this.config.layers[0]) {
              updateFirst = false;
              this.updateLayer(this.config.layers[0], layerConfig);
            } else {
              if (i === 0) updateFirst = false;
              this.addLayer(layerConfig);
            }
          }
        }
      }

      if (!this.config.datasource) {
        this.config.datasource = this.DataSource.get('url');
      }

      if (!this.config.layers || this.config.layers.length === 0) {
        var layer = this.addLayer();
        this._selectPage(layer.id);
      } else {
        if (updateFirst) {
          this.populateDropdown('cube', this.config.layers[0]);
        }

        this._selectPage(this.config.layers[0].id);
      }

      this.loadCubes();
    },

    resize: function() {
      this.Display.resize();
    },

    reset: function() {
      this.config.datasource = null;
      this.config.resultSize = null;
      this.config.timeGroup = 'day';
      this.config.granularity = '90D';
      this.config.timeFrame = {
        start: null,
        end: null
      };
      this.config.display = null;
      this.config.annotation = null;

      if (this.config.layers) {
        var ids = [];
        var activeId;
        for (var i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];
          if (i === 0) {
            this.resetLayer(layer.id);
            activeId = layer.id;
          } else {
            ids.push(layer.id);
          }
        }
        if (ids.length > 0) {
          for (var k = 0; k < ids.length; k++) {
            this.deleteLayer(ids[k]);
          }
        }
        if (activeId) {
          this._selectPage(activeId);
        }
      }
    },

    fullReset: function() {
      this.reset();

      this.update();
      this.load();
    },

    get: function(prop) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      return this[prop];
    }
  };

  Y.Visualizer.Nav = Nav;
}, '1.0', {
  requires: ['node', 'querystring', 'router', 'node-event-simulate', 'async-queue', 'datatype-date',
    'visualizer-component-dropdown', 'visualizer-component-calendars',
    'visualizer-display'
  ]
});

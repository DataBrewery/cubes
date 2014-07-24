YUI.add('visualizer-display', function (Y) {
  Y.namespace('Visualizer');

  var _d3_x_tick_date = d3.time.scale().tickFormat(1);

  var _d3_y_tick_si = function(precision) {
    if (!Y.Lang.isNull(precision) && !Y.Lang.isUndefined(precision)) {
      return function(v) {
        var p = d3.formatPrefix(v);
        return d3.round(p.scale(v), precision).toString() + p.symbol;
      };
    } else {
      return function(v) {
        var p = d3.formatPrefix(v);
        return p.scale(v).toString() + p.symbol;
      };
    }
  };

  var _xDateFormats = {
    'hour': function(d) { return Y.Date.format(new Date(d), { format: '%b %d %H:%M' }); },
    'minute': function(d) { return Y.Date.format(new Date(d), { format: '%b %d %H:%M' }); },
    'day': function(d) { return Y.Date.format(new Date(d), { format: '%b %d %Y' }); },
    'week': function(d) { return Y.Date.format(new Date(d), { format: '%b %d %Y' }); },
    'month': function(d) { return Y.Date.format(new Date(d), { format: '%b %Y' }); },
    'quarter': function(d) { var dd = new Date(d); return 'Q' + (Math.floor(d.getMonth() / 3) + 1) + ' ' + d.getFullYear(); },
    'year': function(d) { return Y.Date.format(new Date(d), { format: '%Y' }); },
    'default': function(d) { return Y.Date.format(new Date(d), { format: '%b %d' }); }
  };

  var _xTickDateFormats = {
    'quarter': _xDateFormats.quarter,
    'default': _d3_x_tick_date
  };

  function xDateFormat(timeGroup) {
    var f = _xDateFormats[timeGroup];
    return f || _xDateFormats['default'];
  }

  function xTickDateFormat(timeGroup) {
    var f = _xTickDateFormats[timeGroup];
    return f || _xTickDateFormats['default'];
  }

  function parseDate(str) {
    if (Y.Lang.isNull(str) || Y.Lang.isUndefined(str))
        return null;
    var parts = str.split(/[- :]/);
    if ( parts.length < 3 )
        return null;
    while ( parts.length < 6 )
        parts.push(0);
    return new Date(parts[0], parts[1]-1, parts[2], parts[3], parts[4], parts[5]);
  }

  function objectSize(obj) {
    var size = 0, key;
    for (key in obj) {
        if (obj.hasOwnProperty(key)) size++;
    }
    return size;
  }

  var Display = function(el, titleEl, dataLayer) {
    this.DEFAULT_MARGIN = { top: 20, right: 40, bottom: 40, left: 100 };
    this.node = el ? Y.one(el) : Y.one('body');
    this.titleNode = titleEl ? Y.one(titleEl) : null;
    this.DataLayer = dataLayer ? dataLayer : new Y.Visualizer.DataLayer();
    this.config = null;
    this.viz = null;
  };

  Display.prototype = {
    _totalFormatter: function(total) {
      var measType = this.DataLayer.get('type');
      var tmpStr = total.toString();
      var dataDisplay;

      var useDecimals = false;

      if (tmpStr.indexOf('.') !== -1) {
        if (tmpStr.length - tmpStr.indexOf('.') - 1 > 2) {
          useDecimals = true;
        } else {
          useDecimals = false;
        }
      } else {
        useDecimals = false;
      }

      var prefix = '', suffix = '';
      if (!Y.Lang.isUndefined(measType) && !Y.Lang.isNull(measType)) {
        if (measType === 'money') {
          prefix = '$';
        } else if (measType === 'percent') {
          total *= 100;
          suffix = '%';
        }
      }

      if (useDecimals) {
        dataDisplay = Y.Number.format(total, {
          prefix: prefix,
          decimalPlaces: 2,
          decimalSeperator: '.',
          thousandsSeparator: ',',
          suffix: suffix
        });
      } else {
        dataDisplay = Y.Number.format(total, {
          prefix: prefix,
          decimalPlaces: 0,
          thousandsSeparator: ',',
          suffix: suffix
        });
      }

      return dataDisplay;
    },

    _renderText: function() {
      var data = this.DataLayer.get('data');

      function textFill(node, options) {
        var multiplier;
        var text = node.getHTML();
        var oldFontSize = parseInt(node.getStyle('font-size'), 10);
        node.setHTML('');

        var container = Y.Node.create('<span>').setStyle('display', 'inline-block').setHTML(text).appendTo(node);
        var min = 1, max = 500, fontSize;
        do {
            fontSize = (max + min) / 2;
            container.setStyle('font-size', fontSize + 'px');

            multiplier = parseInt(node.getComputedStyle('height'), 10) / parseInt(container.getComputedStyle('height'), 10);
            if (multiplier === 1) {
              min = max = fontSize;
            } else if (multiplier > 1) {
              min = fontSize;
            } else {
              max = fontSize;
            }
        } while ((max - min) > 1);

        fontSize = min;

        if (parseInt(node.getComputedStyle('width'), 10) < parseInt(container.getComputedStyle('width'), 10)) {
          min = 1;
          do {
            fontSize = (max + min) / 2;
            container.setStyle('font-size', fontSize + 'px');

            multiplier = parseInt(node.getComputedStyle('width'), 10) / parseInt(container.getComputedStyle('width'), 10);
            if (multiplier === 1) {
              min = max = fontSize;
            } else if (multiplier > 1) {
              min = fontSize;
            } else {
              max = fontSize;
            }
          } while ((max - min) > 1);

          fontSize = min;
        }

        container.remove();
        node.setHTML(text);

        var minFontSize = options.minFontPixels;
        var maxFontSize = options.maxFontPixels;
        var newFontSize = minFontSize && (minFontSize > fontSize) ?
                          minFontSize :
                          maxFontSize && (maxFontSize < fontSize) ?
                          maxFontSize :
                          fontSize;

        node.setStyle('font-size', newFontSize + 'px');
      }

      var wrapper = Y.Node.create('<div>').addClass('single-wrapper');
      var content = Y.Node.create('<div>').addClass('single-content');
      wrapper.append(content);
      this.node.append(wrapper);

      var total;
      if (Y.Lang.isUndefined(data.count) || Y.Lang.isNull(data.count)) {
        total = 0;
      } else {
        total = data.count;
      }

      var dataDisplay = this._totalFormatter(total);

      content.setHTML(dataDisplay);
      textFill(content, { minFontPixels: 20 });

      Y.on('windowresize', Y.bind(function(e) {
        if (this.node.one('.single-content')) {
          textFill(this.node.one('.single-content'), { minFontPixels: 20 });
        }
      }, this));

      return content;
    },

    _renderDiscreteBar: function() {
      var data = this.DataLayer.get('data');

      var chart = rsc.charts.discreteBar(this.node.getDOMNode())
        .margin(this.DEFAULT_MARGIN)
        .x(Y.bind(this._seriesFormat, this))
        .y(function(d) { return d.count; })
        .yTickFormat(Y.bind(this._yTickFormat, this))
        .data(data)
        .render();

      chart.wrapper.selectAll('.bar').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d.key,
              data: d
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      // chart.dispatch
      //   .on('dblclick', function(d) {
      //     Y.fire('visualizer:drilldown', {
      //       key: d.key,
      //       data: d
      //     });
      //   });

      return chart;
    },

    _renderPie: function(donut) {
      var data = this.DataLayer.get('data');

      var chart = rsc.charts.pie(this.node.getDOMNode())
        .x(Y.bind(this._seriesFormat, this))
        .y(function(d) { return d.count; })
        .yTickFormat(Y.bind(this._yTickFormat, this))
        .donut(donut ? true : false)
        .legendToggle(false)
        .data(data)
        .render();

      chart.wrapper.selectAll('.rsc-legend .series').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d.key,
              data: d
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      chart.wrapper.selectAll('.slice').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d.data.key,
              data: d.data
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      // chart.dispatch
      //   .on('dblclick', function(d) {
      //     Y.fire('visualizer:drilldown', {
      //       key: d.data.key,
      //       data: d.data
      //     });
      //   });

      return chart;
    },

    _renderLine: function(type) {
      var data = this.DataLayer.get('data');

      var chart = rsc.charts.line(this.node.getDOMNode())
        .margin(this.DEFAULT_MARGIN)
        .x(function(d) { return parseDate(d.dt); })
        .y(function(d) { return d.count; })
        .xFormat(xDateFormat(this.config.timeGroup))
        .xTickFormat(xTickDateFormat(this.config.timeGroup))
        .index(type === 'index')
        .yFormat(type === 'index' ? null : Y.bind(this._yFormat, this))
        .yTickFormat(type === 'index' ? null : Y.bind(this._yTickFormat, this))
        .seriesFormat(Y.bind(this._seriesFormat, this))
        .legendToggle(false)
        .legend(this._displayLegend())
        .annotate(true)
        .data(data)
        .render();

      if (this.config.annotation) {
        chart.drawAnnotation(this.config.annotation);
      }

      chart.wrapper.selectAll('.focus .point, .rsc-legend .series').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d.key,
              data: d
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      chart.wrapper.selectAll('.focus .line').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d[0].key,
              data: d[0]
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      // chart.dispatch
      //   .on('dblclick', function(d) {
      //     Y.fire('visualizer:drilldown', {
      //       key: d.key,
      //       data: d
      //     });
      //   })
      //   .on('path_dblclick', function(d) {
      //     Y.fire('visualizer:drilldown', {
      //       key: d[0].key,
      //       data: d[0]
      //     });
      //   });

      chart.dispatch.on('annotate', function(cfg) {
        Y.fire('visualizer:annotate', cfg);
      });

      return chart;
    },

    _renderArea: function(type) {
      var data = this.DataLayer.get('data');

      var chart = rsc.charts.area(this.node.getDOMNode())
        .margin(this.DEFAULT_MARGIN)
        .x(function(d) { return parseDate(d.dt); })
        .y(function(d) { return d.count; })
        .xFormat(xDateFormat(this.config.timeGroup))
        .xTickFormat(xTickDateFormat(this.config.timeGroup))
        .yFormat(type === 'expanded' ? null : Y.bind(this._yFormat, this))
        .yTickFormat(type === 'expanded' ? null : Y.bind(this._yTickFormat, this))
        .seriesFormat(Y.bind(this._seriesFormat, this))
        .stacked(type === 'stacked')
        .expanded(type === 'expanded')
        .streamed(type === 'stream')
        .legendToggle(false)
        .legend(this._displayLegend())
        .annotate(true)
        .data(data)
        .render();

      if (this.config.annotation) {
        chart.drawAnnotation(this.config.annotation);
      }

      chart.wrapper.selectAll('.series').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d.key,
              data: d
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      // chart.dispatch
      //   .on('dblclick', function(d) {
      //     Y.fire('visualizer:drilldown', {
      //       key: d.key,
      //       data: d
      //     });
      //   });

      chart.dispatch.on('annotate', function(cfg) {
        Y.fire('visualizer:annotate', cfg);
      });

      return chart;
    },

    _renderHeatmap: function() {
      var data = this.DataLayer.get('data');

      var chart = rsc.charts.heatmap(this.node.getDOMNode())
        .margin(this.DEFAULT_MARGIN)
        .x(function(d) { return parseDate(d.dt); })
        .y(function(d) { return d.count; })
        .xFormat(xDateFormat(this.config.timeGroup))
        .xTickFormat(xTickDateFormat(this.config.timeGroup))
        .yFormat(Y.bind(this._yFormat, this))
        .yTickFormat(Y.bind(this._yTickFormat, this))
        .seriesFormat(Y.bind(this._seriesFormat, this))
        .legend(false)
        .data(data)
        .render();

      chart.wrapper.selectAll('.tile').each(function(d, i) {
        Y.one(this).on('tap', function(e) {
          var node = e.currentTarget;
          if (new Date() - node.getData('lastTap') < 400) {
            e.preventDefault();

            Y.fire('visualizer:drilldown', {
              key: d.key,
              data: d
            });
          } else {
            node.setData('lastTap', new Date());
          }
        });
      });

      return chart;
    },

    _renderTable: function(DataSource) {
      var i, k,
          data = this.DataLayer.get('data');
          measure = this.config.measure ? this.config.measure : 'record_count';

      function formatTotal(o) {
        return this._totalFormatter(o.value);
      }

      function keyExists(arr, key) {
        var found = false;
        for (var k = 0; k < arr.length; k++) {
          if (arr[k].key === key) {
            found = true;
            break;
          }
        }
        return found;
      }

      function colSort(a, b) {
        return a.index - b.index;
      }

      var table = new Y.DataTable({
        data: data,
        scrollable: 'xy',
        height: '100%',
        width: '100%',
        sortable: true
      });

      // add selection support
      table.addAttr('selectedRow', { value: null });

      table.delegate('tap', function(e) {
        var node = e.currentTarget;
        table.set('selectedRow', node);
        if (new Date() - node.getData('lastTap') < 400) {
          e.preventDefault();

          var rec = table.getRecord(e.currentTarget.getData('yui3-record'));
          var recObj = rec.toJSON();

          Y.fire('visualizer:drilldown', {
            key: recObj[this.config.drilldown],
            data: recObj
          });
        } else {
          node.setData('lastTap', new Date());
        }
      }, '.yui3-datatable-data tr', this);

      table.after('selectedRowChange', function(e) {
        var tr = e.newVal,
            last_tr = e.prevVal;

        if (last_tr) {
          last_tr.removeClass('row-highlight');
        }

        tr.addClass('row-highlight');
      });

      var tableNode = Y.Node.create('<div>').addClass('viz-table yui3-skin-sam');
      this.node.append(tableNode);

      table.render(tableNode.getDOMNode());

      return table;
    },

    _displayLegend: function() {
      var displayLegend = false;
      var data = this.DataLayer.get('data');

      if (data.length > 1) {
        displayLegend = true;
      } else {
        for (var i = 0; i < this.config.layers.length; i++) {
          var layer = this.config.layers[i];

          if (layer.drilldown) {
            displayLegend = true;
            break;
          }
        }
      }

      return displayLegend;
    },

    _seriesFormat: function(d) {
      var data = this.DataLayer.get('data');

      var dKey = d.key;
      if (typeof dKey !== 'string') dKey = dKey + '';

      var uniqueKeys = {};
      for (var i = 0; i < data.length; i++) {
        var tmpKey = data[i].key;
        if (typeof tmpKey !== 'string') tmpKey = tmpKey + '';

        var innerSplitKey = tmpKey.split(' : ');
        var innerKey = innerSplitKey[innerSplitKey.length - 1];
        uniqueKeys[innerKey] = uniqueKeys[innerKey] ? (uniqueKeys[innerKey] + 1) : 1;
      }

      var splitKey = dKey.split(' : ');
      var key = splitKey[splitKey.length - 1];

      for (var uniqueKey in uniqueKeys) {
        if (uniqueKey === key && uniqueKeys[uniqueKey] > 1) {
          return d.key;
        } else if (uniqueKey === key && uniqueKeys[uniqueKey] === 1) {
          return key;
        }
      }

      return d.key;
    },

    _yFormat: function(d) {
      var fmtp = this._yFormatParams(d);
      return Y.Number.format(fmtp.value, {
        prefix: fmtp.prefix,
        decimalPlaces: fmtp.useDecimals ? 2 : 0,
        decimalSeperator: '.',
        thousandsSeparator: ',',
        suffix: fmtp.suffix
      });
    },

    _yTickFormat: function(d) {
      var fmtp = this._yFormatParams(d);
      var dataDisplay = fmtp.prefix + _d3_y_tick_si(fmtp.useDecimals ? 2 : null)(fmtp.value) + fmtp.suffix;
      return dataDisplay;
    },
    
    _yFormatParams: function(d) {
      var measType = this.DataLayer.get('type');
      var yMax = this.DataLayer.get('yMax');

      var useDecimals = false;

      if (yMax > 10) {
        var tmpStr = d.toString();

        if (tmpStr.indexOf('.') !== -1) {
          if (tmpStr.length - tmpStr.indexOf('.') - 1 > 2) {
            useDecimals = true;
          } else {
            useDecimals = false;
          }
        } else {
          useDecimals = false;
        }
      } else {
        useDecimals = true;
      }

      var prefix = '', suffix = '';
      if (!Y.Lang.isUndefined(measType) && !Y.Lang.isNull(measType)) {
        if (measType === 'money') {
          prefix = '$';
        } else if (measType === 'percent') {
          d *= 100;
          suffix = '%';
        }
      }

      return {
        useDecimals: useDecimals,
        prefix: prefix,
        suffix: suffix,
        value: d
      };
    },

    _renderTitle: function(DataSource, display) { // TODO: Update for multiple layers
      if (!this.titleNode) return;

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

      var title = '';

      // if (this.config.cube) {
      //   title += DataSource.getDisplayName(this.config.cube);
      // }

      title += DataSource.getMeasureDisplayName(this.config.cube, this.config.measure);

      if (this.config.drilldown) {
        title += ((this.config.drilldown === DataSource.getSplitDimensionString()) ? ' where ' : ' by ') + DataSource.getDisplayName(this.config.cube, this.config.drilldown);
      }

      if (this.config.filters) {
        for (var i = 0; i < this.config.filters.length; i++) {
          var filter = this.config.filters[i];

          if (filter.disabled) continue;

          title += filter.invert ? ', NOT ' : ', ';

          var filterStr = '';
          for (var k = 0; k < filter.info.length; k++) {
            if (filterStr !== '') filterStr += ' : ';
            filterStr += DataSource.getDisplayName(this.config.cube, filter.info[k].dim) + ' = ' + (filter.info[k].valLabel ? filter.info[k].valLabel : filter.info[k].val);
          }

          title += filterStr;
        }
      }

      if (this.config.timeGroup && (display === 'line' || display === 'index' ||
        display === 'stacked' || display === 'expanded' || display === 'stream' || display === 'heatmap' ||
        display === 'table' || display === 'top' || display === 'bottom'))
      {
        title += ', ' + 'Over ' + this.config.timeGroup;
      }

      if (this.config.granularity) {
        if (this.config.granularity.toLowerCase() === 'custom') {
          title += ', From ' + Y.Date.format(new Date(this.config.timeFrame.start), { format: '%m/%d/%Y' }) +
            ' To ' + Y.Date.format(new Date(this.config.timeFrame.end), { format: '%m/%d/%Y' });
        } else {
          var granInfo = getGranularityInfo(this.config.granularity);
          title += ', Last ' + granInfo.offset + ' ' + granInfo.type + 's';
        }
      }

      this.titleNode.setHTML(title);

      return title;
    },

    render: function(data, config, DataSource) {
      this.config = config;

      if (!Y.Lang.isUndefined(data) && !Y.Lang.isNull(data)) {
        this.DataLayer.load(data, DataSource);
      }

      this.DataLayer.parse(config);

      this.clear();

      var display = this.DataLayer.get('display');

      // if (this.titleNode) this._renderTitle(DataSource, display); // TODO: Re-enable when support for multiple layers

      if (Y.Lang.isUndefined(display) || Y.Lang.isNull(display) || display === 'text') {
        this.viz = this._renderText();
      } else if (display === 'bar') {
        this.viz = this._renderDiscreteBar();
      } else if (display === 'pie') {
        this.viz = this._renderPie();
      } else if (display === 'donut') {
        this.viz = this._renderPie(true);
      } else if (display === 'line') {
        this.viz = this._renderLine();
      } else if (display === 'index') {
        this.viz = this._renderLine('index');
      } else if (display === 'stacked') {
        this.viz = this._renderArea('stacked');
      } else if (display === 'expanded') {
        this.viz = this._renderArea('expanded');
      } else if (display === 'stream') {
        this.viz = this._renderArea('stream');
      } else if (display === 'heatmap') {
        this.viz = this._renderHeatmap();
      } else if (display === 'table' || display === 'top' || display === 'bottom') {
        this.viz = this._renderTable(DataSource);
      }
    },

    clear: function() {
      this.viz = null;

      if (this.titleNode) {
        this.titleNode.setHTML('');
      }

      this.node.get('childNodes').remove();
    },

    resize: function() {
      if (this.viz) {
        var display = this.DataLayer.get('display');

        if (Y.Lang.isUndefined(display) || Y.Lang.isNull(display) || display === 'text') {
          this.viz = this._renderText();
        } else if (display === 'table' || display === 'top' || display === 'bottom') {
          this.viz.syncUI();
        } else {
          this.viz.resize();
        }
      }
    },

    get: function(prop) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      return this[prop];
    }
  };

  Y.Visualizer.Display = Display;
}, '1.0', {
  requires: ['node', 'datatype', 'datatable', 'datatable-sort', 'datatable-scroll', 'event-tap']
});

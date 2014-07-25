rsc = (function(){var rsc = {
  version: '0.0.1'
};rsc.utils = {};

rsc.utils.generateUUID = function(x, y, parent, content) {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
    return v.toString(16);
  });
};

rsc.utils.stringToHashCode = function(str) {
  var hash = 0, i, char;
  if (str.length === 0) return hash;
  for (i = 0, l = str.length; i < l; i++) {
    char  = str.charCodeAt(i);
    hash  = ((hash<<5)-hash)+char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash);
};

rsc.utils.deepCopy = function(o) {
  var copy = o,k;

  if (o && typeof o === 'object') {
    copy = Object.prototype.toString.call(o) === '[object Array]' ? [] : {};
    for (k in o) {
      copy[k] = rsc.utils.deepCopy(o[k]);
    }
  }

  return copy;
};

rsc.utils.convertDateToUTC = function(date) {
  return new Date(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds());
};

rsc.utils.multiTimeFormat = function(d) {
  var format = d3.time.format.multi([
    [".%L", function(d) { return d.getMilliseconds(); }],
    [":%S", function(d) { return d.getSeconds(); }],
    ["%I:%M", function(d) { return d.getMinutes(); }],
    ["%I %p", function(d) { return d.getHours(); }],
    ["%a %d", function(d) { return d.getDay() && d.getDate() != 1; }],
    ["%b %d", function(d) { return d.getDate() != 1; }],
    ["%B", function(d) { return d.getMonth(); }],
    ["%Y", function(d) { return true; }]
  ]);

  return format(typeof d === 'object' ? d : rsc.utils.convertDateToUTC(new Date(d)));
};

rsc.utils.timeFormat = function(d) {
  var format = d3.time.format('%x %X');
  return format(typeof d === 'object' ? d : rsc.utils.convertDateToUTC(new Date(d)));
};

rsc.utils.unitSuffixFormat = function(d) {
  var prefix = d3.formatPrefix(d);
  return Number(prefix.scale(d).toFixed(2)) + prefix.symbol;
};
rsc.tooltip = {};

rsc.tooltip.show = function(x, y, parent, content) {
  var tooltip = parent.select('.rsc-tooltip');
  if (!tooltip.node()) {
    tooltip = parent.append('div')
      .attr('class', 'rsc-tooltip')
      .style('left', '0')
      .style('top', '0');
  }

  tooltip
    .style('opacity', '0')
    .html(content);

  var left = x - tooltip.node().clientWidth / 2,
    top = y - tooltip.node().clientHeight - 10,
    parentWidth = parseInt(parent.style('width'), 10);

  if (left < 0) {
    left = 0;
  } else if (left + tooltip.node().clientWidth > parentWidth) {
    left = parentWidth - tooltip.node().clientWidth;
  }
  if (top < 0) {
    top = 0;
  }

  tooltip
    .style('left', left + 'px')
    .style('top', top + 'px')
    .style('opacity', 1);
};

rsc.tooltip.update = function(x, y, parent) {
  var tooltip = parent.select('.rsc-tooltip');

  var left = x - tooltip.node().clientWidth / 2,
    top = y - tooltip.node().clientHeight - 10,
    parentWidth = parseInt(parent.style('width'), 10);

  if (left < 0) {
    left = 0;
  } else if (left + tooltip.node().clientWidth > parentWidth) {
    left = parentWidth - tooltip.node().clientWidth;
  }
  if (top < 0) {
    top = 0;
  }

  tooltip
    .style('left', left + 'px')
    .style('top', top + 'px');
};

rsc.tooltip.hide = function(parent) {
  var tooltips = parent.selectAll('.rsc-tooltip');

  tooltips
    .style('opacity', 0);
};

rsc.tooltip.remove = function(parent) {
  var tooltips = parent.selectAll('.rsc-tooltip');

  tooltips.remove();
};
rsc.interact = {};

rsc.interact.mouseover = function(nodesToIterate, nodeToCompare, nodesToChange, tooltipInfo) {
  if (nodesToIterate) {
    nodesToIterate.each(function() {
      var nodes;

      if (typeof nodesToChange === 'function') {
        nodes = nodesToChange(this);
      } else {
        nodes = nodesToChange ? nodesToChange : d3.select(this);
      }

      if (this !== nodeToCompare) {
        nodes
          .classed('faded', true)
          .classed('bolden', false);
      } else {
        nodes
          .classed('faded', false)
          .classed('bolden', true);
      }
    });
  }

  if (tooltipInfo) {
    var mouse = d3.mouse(tooltipInfo.wrapper.node());
    rsc.tooltip.show(
      mouse[0],
      mouse[1],
      tooltipInfo.wrapper,
      tooltipInfo.text
    );
  }
};

rsc.interact.mouseout = function(nodes, tooltipWrapper) {
  if (nodes) {
    nodes
      .classed('faded', false)
      .classed('bolden', false);
  }

  if (tooltipWrapper) {
    rsc.tooltip.hide(tooltipWrapper);
  }
};

rsc.interact.mousemove = function(tooltipWrapper) {
  if (tooltipWrapper) {
    var mouse = d3.mouse(tooltipWrapper.node());
    rsc.tooltip.update(
      mouse[0],
      mouse[1],
      tooltipWrapper
    );
  }
};
rsc.legend = function(_chart) {
  this._chart = _chart;

  this.height = 21;
  this.padding = 5;
  this.node = null;

  var _key = function(d) { return d.key; };
  this.key = function(key) {
    if (typeof key !== 'undefined') {
      _key = key;

      return this;
    } else {
      return _key;
    }
  };

  this.render = function(wrapper) {
    var legendNode = wrapper.select('.rsc-legend');

    if (!legendNode.node()) {
      legendNode = wrapper.insert('div', 'svg')
        .attr('class', 'rsc-legend');

      legendNode.append('div')
        .attr('class', 'rsc-legend-inner')
          .append('div')
            .attr('class', 'expand-toggle');

      this.node = legendNode;
    }

    legendNode
      .style('height', (this.height + 7) + 'px')
      .style('margin-top', this._chart.margin().top + 'px')
      .style('margin-left', this._chart.margin().left + 'px')
      .style('margin-right', this._chart.margin().right + 'px');

    legendNode.select('.rsc-legend-inner')
      .style('height', this.height + 'px')
      .style('max-width', this._chart.width() + 'px');

    legendNode.select('.expand-toggle')
      .style('height', this.height + 'px')
      .on('click', function() {
        this.expandToggle();
      }.bind(this));

    return this;
  };

  this.update = function() {
    var self = this,
      innerNode = this.node.select('.rsc-legend-inner');

    var series = innerNode.selectAll('.series')
      .data(this._chart.data(), function(d) { return this.key()(d); }.bind(this));

    seriesNodes = series.enter().append('div')
      .attr('class', 'series')
        .on('click', function(d, i) {
          if (this._chart.legendToggle()) {
            if (d.disabled) {
              d.disabled = false;
            } else {
              d.disabled = true;
            }
            this._chart.dispatch.legend_click(d, i);
            this._chart.update();
          } else {
            this._chart.dispatch.legend_click(d, i);
          }
        }.bind(this))
        .on('dblclick', function(d, i) {
          this._chart.dispatch.legend_dblclick(d, i);
        }.bind(this));

    series.exit().remove();

    series.sort(function(a, b) {
      if (a.values && b.values) {
        return d3.descending(
          d3.median(a.values, function(d) { return self._chart.y()(d); }),
          d3.median(b.values, function(d) { return self._chart.y()(d); })
        );
      } else {
        return d3.descending(
          self._chart.y()(a),
          self._chart.y()(b)
        );
      }
    });

    seriesNodes
      .append('div')
        .style('border-color', function(d, i) { return self._chart.color()(rsc.utils.stringToHashCode(self.key()(d))); });

    innerNode.selectAll('.series div')
      .style('background-color', function(d) {
        if (d.disabled) {
          return 'transparent';
        } else {
          return d3.select(this).style('border-color');
        }
      });

    seriesNodes
      .append('span')
        .html(this.key());

    innerNode.selectAll('.series span')
      .style('opacity', function(d) {
        if (d.disabled) {
          return 0.5;
        } else {
          return 1;
        }
      });

    this.expandToggle(false);
    if (innerNode.node().scrollHeight <= innerNode.node().offsetHeight) {
      innerNode.select('.expand-toggle').classed('toggle-hidden', true);
    } else {
      innerNode.select('.expand-toggle').classed('toggle-hidden', false);
    }

    return this;
  };

  this.remove = function() {
    if (this.node) {
      this.node.remove();
    }
  };

  this.expandToggle = function(expand) {
    var node = this.node.select('.rsc-legend-inner');

    if (expand === true || expand === false) {
      node.classed('expand', expand);
    } else {
      if (node.classed('expand')) {
        node.classed('expand', false);
      } else {
        node.classed('expand', true);
      }
    }
  };

  this.getHeight = function() {
    return this.node.node().offsetHeight;
  };

  return this;
};
rsc.annotate = function(_chart) {
  this._chart = _chart;

  this.node = this._chart.wrapper.append('div').attr('class', 'rsc-annotate').style('display', 'none');
  this.config = this._chart.wrapper.append('div').attr('class', 'rsc-annotate-config').style('display', 'none');

  this.color = '#ff0000';
  this.stroke = '4px';
  this.opacity = 0.3;

  // build config window
  this.config.append('div').html('Color').append('input')
    .attr('type', 'text').attr('class', 'color').property('value', this.color).on('input', function() {
      self.node.style('border-color', d3.select(this).property('value'));
    });
  this.config.append('div').html('Stroke Width').append('input')
    .attr('type', 'text').attr('class', 'stroke').property('value', this.stroke).on('input', function() {
      self.node.style('border-width', d3.select(this).property('value'));
    });
  this.config.append('div').attr('class', 'rsc-annotate-button').html('Okay').on('click', function() {
    self.color = self.config.select('.color').property('value');
    self.stroke = self.config.select('.stroke').property('value');

    self.config.style('display', 'none');

    self._chart.dispatch.annotate({
      color: self.color,
      stroke: self.stroke,
      bbox: self.getBBox()
    });
  });

  var self = this;
  var _mousedown = false;
  var _drawn = false;
  var _md = null;
  var _mm = null;

  this.init = function() {
    self._chart.wrapper.select('.rsc-canvas')
      .on('mousedown', function() {
        self.mousedown();
      })
      .on('mouseup', function() {
        self.mouseup();
      })
      .on('mousemove', function() {
        self.mousemove();
      });
  };

  this.mousedown = function() {
    if (!self._chart.annotate()) return;

    var node = self._chart.wrapper.select('.rsc-canvas').node();
    var mouse = d3.mouse(node);
    var chartMargin = self._chart.getChartMargin();
    mouse[0] -= chartMargin.left;
    mouse[1] -= chartMargin.top;

    _md = [self._chart._xScale.invert(mouse[0]), self._chart._yScale.invert(mouse[1])];

    if (_md[0] < self._chart._xScale.domain()[0] || _md[0] > self._chart._xScale.domain()[1]) return;
    if (_md[1] < self._chart._yScale.domain()[0] || _md[1] > self._chart._yScale.domain()[1]) return;

    _mousedown = true;
    _drawn = false;

    self.node.style('display', 'none');
    self.config.style('display', 'none');
  };

  this.mouseup = function() {
    if (!self._chart.annotate()) return;

    _mousedown = false;

    if (_drawn) {
      var node = self._chart.wrapper.select('.rsc-canvas').node();
      var mouse = d3.mouse(node);
      mouse[0] += node.offsetLeft;
      mouse[1] += node.offsetTop;

      self.popupConfig(mouse);
    }
  };

  this.mousemove = function() {
    if (!self._chart.annotate() || !_mousedown) return;

    var node = self._chart.wrapper.select('.rsc-canvas').node();
    var mouse = d3.mouse(node);
    var chartMargin = self._chart.getChartMargin();
    mouse[0] -= chartMargin.left;
    mouse[1] -= chartMargin.top;

    _mm = [self._chart._xScale.invert(mouse[0]), self._chart._yScale.invert(mouse[1])];

    self.draw(self.getBBox());
  };

  this.popupConfig = function(pos) {
    this.config.select('.color').property('value', this.color);
    this.config.select('.stroke').property('value', this.stroke);

    this.config
      .style('display', null);

    var left = pos[0] + 10;
    var top = pos[1];

    if (left + parseInt(this.config.style('width'), 10) > parseInt(self._chart.wrapper.style('width'), 10)) {
      left = parseInt(self._chart.wrapper.style('width'), 10) - parseInt(this.config.style('width'), 10) - 10;
    }
    if (top + parseInt(this.config.style('height'), 10) > parseInt(self._chart.wrapper.style('height'), 10)) {
      top = parseInt(self._chart.wrapper.style('height'), 10) - parseInt(this.config.style('height'), 10) - 10;
    }

    this.config
      .style('left', left + 'px')
      .style('top', top + 'px');
  };

  this.getBBox = function() {
    if (!_md) {
      return null;
    } else {
      return _md.concat(_mm); // x0, y0, x1, y1
    }
  };

  this.render = function(cfg) {
    if (!cfg.bbox) return;

    if (cfg.color) this.color = cfg.color;
    if (cfg.stroke) this.stroke = cfg.stroke;

    _md = cfg.bbox.slice(0, 2);
    _mm = cfg.bbox.slice(2);

    this.draw(cfg.bbox, false, true);
  };

  this.draw = function(bbox, transition, opacityChange) {
    var node = self._chart.wrapper.select('.rsc-canvas').node();
    var chartMargin = self._chart.getChartMargin();

    var x0 = self._chart._xScale(bbox[0]);
    var y0 = self._chart._yScale(bbox[1]);
    var x1 = self._chart._xScale(bbox[2]);
    var y1 = self._chart._yScale(bbox[3]);

    if (Math.abs(x0 - x1) < 10 && Math.abs(y0 - y1) < 10) return;

    _drawn = true;

    self.node
      .style('display', null);

    if (opacityChange) self.node.style('opacity', 0);

    if (transition) {
      self.node.transition().duration(self._chart.duration())
        .style('opacity', self.opacity)
        .style('border-color', self.color)
        .style('border-width', self.stroke)
        .style('left', (Math.min(x0, x1) + node.offsetLeft + chartMargin.left) + 'px')
        .style('top', (Math.min(y0, y1) + node.offsetTop + chartMargin.top) + 'px')
        .style('width', Math.abs(x0 - x1) + 'px')
        .style('height', Math.abs(y0 - y1) + 'px');
    } else {
      self.node
        .style('border-color', self.color)
        .style('border-width', self.stroke)
        .style('left', (Math.min(x0, x1) + node.offsetLeft + chartMargin.left) + 'px')
        .style('top', (Math.min(y0, y1) + node.offsetTop + chartMargin.top) + 'px')
        .style('width', Math.abs(x0 - x1) + 'px')
        .style('height', Math.abs(y0 - y1) + 'px');

      if (this._chart.transition()) {
        self.node.transition().duration(self._chart.duration())
          .style('opacity', self.opacity);
      } else {
        self.node.style('opacity', self.opacity);
      }
    }
  };

  this.update = function() {
    var bbox = this.getBBox();

    if (bbox) this.draw(bbox, this._chart.transition());
  };

  return this;
};
rsc.charts = {};rsc.charts.base = function(parent) {
  var _parent = parent || 'body';

  var _chart = {};

  var THEMES = ['light', 'dark'];

  var _theme = 'light';
  var _data = [];
  var _margin = { top: 20, right: 20, bottom: 40, left: 40 };
  var _width = parseInt(d3.select(_parent).style('width'), 10) - _margin.left - _margin.right;
  var _height = parseInt(d3.select(_parent).style('height'), 10) - _margin.top - _margin.bottom;
  var _x = function(d) { return d[0]; };
  var _y = function(d) { return d[1]; };
  var _xTickFormat;
  var _xFormat;
  var _yTickFormat;
  var _yFormat;
  var _color = d3.scale.category20();
  // RAIN COLORS
  // var _color = d3.scale.ordinal().range([
  //   '#8e9493', '#bfc9be', '#5b859a', '#a4bfd7',
  //   '#59575f', '#144056', '#978290', '#263036'
  // ]);
  var _transition = true;
  var _duration = 750;
  var _tooltips = true;
  var _grid = true;
  var _legend = true;
  var _legendToggle = true;

  _chart.parent = function(parent) {
    if (typeof parent !== 'undefined' && parent !== null) {
      _parent = parent;

      return this;
    } else if (parent === null) {
      return this;
    } else {
      return _parent;
    }
  };

  _chart.theme = function(theme) {
    if (typeof theme !== 'undefined' && theme !== null) {
      if (THEMES.indexOf(theme) !== -1) {
        var oldTheme = _theme;
        _theme = theme;

        if (_chart.wrapper) {
          _chart.wrapper.classed('rsc-theme-' + oldTheme, false);
          _chart.wrapper.classed('rsc-theme-' + _theme, true);
        }
      }

      return this;
    } else if (theme === null) {
      return this;
    } else {
      return _theme;
    }
  };

  _chart.data = function(data) {
    if (typeof data !== 'undefined') {
      data = rsc.utils.deepCopy(data);
      _data = Object.prototype.toString.call(data) !== '[object Array]' ? [data] : data;

      return this;
    } else {
      return _data;
    }
  };

  _chart.margin = function(margin) {
    if (typeof margin !== 'undefined' && margin !== null) {
      var oldWidth = _width + _margin.top + _margin.bottom;
      var oldHeight = _height + _margin.left + _margin.right;

      if (typeof margin.top !== 'undefined') _margin.top = margin.top;
      if (typeof margin.right !== 'undefined') _margin.right = margin.right;
      if (typeof margin.bottom !== 'undefined') _margin.bottom = margin.bottom;
      if (typeof margin.left !== 'undefined') _margin.left = margin.left;

      this.width(oldWidth);
      this.height(oldHeight);

      return this;
    } else if (margin === null) {
      return this;
    } else {
      return {
        top: _margin.top,
        right: _margin.right,
        bottom: _margin.bottom,
        left: _margin.left
      };
    }
  };

  _chart.width = function(width) {
    if (typeof width !== 'undefined' && width !== null) {
      _width = width - _margin.left - _margin.right;

      return this;
    } else if (width === null) {
      return this;
    } else {
      return _width - 4;
    }
  };

  _chart.height = function(height) {
    if (typeof height !== 'undefined' && height !== null) {
      _height = height - _margin.top - _margin.bottom;

      return this;
    } else if (height === null) {
      return this;
    } else {
      return _height - 3;
    }
  };

  _chart.x = function(x) {
    if (typeof x !== 'undefined' && x !== null) {
      _x = x;

      return this;
    } else if (x === null) {
      return this;
    } else {
      return _x;
    }
  };

  _chart.y = function(y) {
    if (typeof y !== 'undefined' && y !== null) {
      _y = y;

      return this;
    } else if (y === null) {
      return this;
    } else {
      return _y;
    }
  };

  _chart.xTickFormat = function(xTickFormat) {
    if (typeof xTickFormat !== 'undefined') {
      _xTickFormat = xTickFormat;

      return this;
    } else if (xTickFormat === null) {
      return this;
    } else {
      return _xTickFormat;
    }
  };

  _chart.xFormat = function(xFormat) {
    if (typeof xFormat !== 'undefined') {
      _xFormat = xFormat;

      return this;
    } else if (xFormat === null) {
      return this;
    } else {
      return _xFormat;
    }
  };

  _chart.yTickFormat = function(yTickFormat) {
    if (typeof yTickFormat !== 'undefined') {
      _yTickFormat = yTickFormat;

      return this;
    } else if (yTickFormat === null) {
      return this;
    } else {
      return _yTickFormat;
    }
  };

  _chart.yFormat = function(yFormat) {
    if (typeof yFormat !== 'undefined') {
      _yFormat = yFormat;

      return this;
    } else if (yFormat === null) {
      return this;
    } else {
      return _yFormat;
    }
  };

  _chart.color = function(color) {
    if (typeof color !== 'undefined' && color !== null) {
      _color = color;

      return this;
    } else if (color === null) {
      return this;
    } else {
      return _color;
    }
  };

  _chart.transition = function(transition) {
    if (typeof transition !== 'undefined') {
      _transition = transition;

      return this;
    } else {
      return _transition;
    }
  };

  _chart.duration = function(duration) {
    if (typeof duration !== 'undefined') {
      _duration = duration;

      return this;
    } else {
      return _duration;
    }
  };

  _chart.tooltips = function(tooltips) {
    if (typeof tooltips !== 'undefined') {
      _tooltips = tooltips;

      return this;
    } else {
      return _tooltips;
    }
  };

  _chart.grid = function(grid) {
    if (typeof grid !== 'undefined') {
      _grid = grid;

      return this;
    } else {
      return _grid;
    }
  };

  _chart.legend = function(legend) {
    if (typeof legend !== 'undefined') {
      _legend = legend;

      return this;
    } else {
      return _legend;
    }
  };

  _chart.legendToggle = function(legendToggle) {
    if (typeof legendToggle !== 'undefined') {
      _legendToggle = legendToggle;

      return this;
    } else {
      return _legendToggle;
    }
  };

  _chart.update = function(data) {
    if (typeof data !== 'undefined') {
      this.data(rsc.utils.deepCopy(data)).render(true);
    } else {
      this.render(true);
    }

    if (this.modules.annotate) {
      this.modules.annotate.update();
    }

    return this;
  };

  _chart.resize = function() {
    this.width(parseInt(d3.select(_parent).style('width'), 10));
    this.height(parseInt(d3.select(_parent).style('height'), 10));

    this.update();
  };

  _chart.dispatch = d3.dispatch(); // placeholder
  _chart.wrapper = d3.select(_parent).append('div').attr('class', 'rsc-wrapper rsc-theme-' + _theme);

  _chart.modules = {
    legend: new rsc.legend(_chart)
  };

  _chart.getChartHeight = function() {
    return this.legend() ? this.height() - this.modules.legend.getHeight() - this.modules.legend.padding : this.height();
  };

  _chart.getChartWidth = function() {
    return this.width();
  };

  _chart.getChartMargin = function() {
    return {
      top: this.legend() ? this.modules.legend.padding : this.margin().top,
      bottom: this.margin().bottom,
      left: this.margin().left,
      right: this.margin().right
    };
  };

  return _chart;
};
rsc.charts.area = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove', 'legend_click', 'legend_dblclick', 'annotate');

  var _clipId = 'clip_' + rsc.utils.generateUUID();

  var _stacked = false;
  var _streamed = false;
  var _expanded = false;
  var _seriesFormat = function(d) { return d.key; };
  var _annotate = false;

  chart.modules.annotate = new rsc.annotate(chart);

  chart.stacked = function(stacked) {
    if (typeof stacked !== 'undefined') {
      _stacked = stacked;

      return this;
    } else {
      return _stacked;
    }
  };

  chart.streamed = function(streamed) {
    if (typeof streamed !== 'undefined') {
      _streamed = streamed;

      return this;
    } else {
      return _streamed;
    }
  };

  chart.expanded = function(expanded) {
    if (typeof expanded !== 'undefined') {
      _expanded = expanded;

      return this;
    } else {
      return _expanded;
    }
  };

  chart.seriesFormat = function(seriesFormat) {
    if (typeof seriesFormat !== 'undefined') {
      if (seriesFormat === null) {
        _seriesFormat = function(d) { return d.key; };
      } else {
        _seriesFormat = seriesFormat;
      }

      return this;
    } else {
      return _seriesFormat;
    }
  };

  chart.annotate = function(annotate) {
    if (typeof annotate !== 'undefined') {
      _annotate = annotate;

      return this;
    } else {
      return _annotate;
    }
  };

  chart.drawAnnotation = function(annotationConfig) {
    if (!this.annotate()) return;

    this.modules.annotate.render(annotationConfig);
  };

  chart.xTickFormat(rsc.utils.multiTimeFormat);

  chart.render = function(update) {
    var x, y, xAxis, yAxis, emptyArea, area, chartData,
      svg, series, paths, h, w, m,
      self = this;

    if (this.legend()) {
      this.modules.legend.key(this.seriesFormat());
      this.modules.legend.render(this.wrapper);
    } else {
      this.modules.legend.remove();
    }

    h = this.getChartHeight();
    w = this.getChartWidth();
    m = this.getChartMargin();

    x = d3.time.scale()
      .range([0, w]);

    this._xScale = x;

    y = d3.scale.linear()
      .range([h, 0]);

    this._yScale = y;

    xAxis = d3.svg.axis()
      .scale(x)
      .orient('bottom');

    xAxis.tickFormat(this.xTickFormat());

    yAxis = d3.svg.axis()
      .scale(y)
      .orient('left');

    if (this.expanded()) {
      yAxis.tickFormat(function(v) { return (v * 100) + '%'; });
    } else if (this.yTickFormat()) {
      yAxis.tickFormat(this.yTickFormat());
    } else {
      yAxis.tickFormat(rsc.utils.unitSuffixFormat);
    }

    if (this.grid()) {
      xAxis.tickSize(-h);
      yAxis.tickSize(-w);
    }

    emptyArea = d3.svg.area()
      .x(function(d) { return x(self.x()(d)); })
      .y0(h)
      .y1(h)
      .interpolate('linear');

    area = d3.svg.area()
      .x(function(d) { return x(self.x()(d)); })
      .interpolate('linear');

    if (this.stacked() || this.streamed() || this.expanded()) {
      area
        .y0(function(d) { return y(d.y0); })
        .y1(function(d) { return y(d.y0 + d.y); });

      var stack = d3.layout.stack()
        .values(function(d) { return d.values; })
        .x(self.x())
        .y(self.y());

      if (this.streamed()) {
        stack.offset('wiggle');
        stack.order('inside-out');
      } else if (this.expanded()) {
        stack.offset('expand');
        stack.order('default');
      } else {
        stack.offset('zero');
        stack.order('default');
      }

      chartData = stack(this.data().filter(function(d) { return !d.disabled; }));

      if (this.expanded()) {
        y.domain([0, 1]);
      } else {
        y.domain([
          d3.min([0, d3.min(chartData, function(s) { return d3.min(s.values, self.y()); })]),
          d3.max(chartData, function(s) { return d3.max(s.values, function(d) { return d.y0 + d.y; }); })
        ]);
      }
    } else {
      area
        .y0(h)
        .y1(function(d) { return y(self.y()(d)); });

      chartData = this.data().filter(function(d) { return !d.disabled; });

      y.domain([
        d3.min([0, d3.min(chartData, function(s) { return d3.min(s.values, self.y()); })]),
        d3.max(chartData, function(s) { return d3.max(s.values, self.y()); })
      ]);
    }

    x.domain([
      d3.min(chartData, function(s) { return d3.min(s.values, self.x()); }),
      d3.max(chartData, function(s) { return d3.max(s.values, self.x()); })
    ]);

    svg = this.wrapper.select('.rsc-inner-wrapper');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('class', 'rsc-canvas')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom)
        .append('g')
          .attr('class', 'rsc-inner-wrapper')
          .attr('transform', 'translate(' + m.left + ',' + m.top + ')');

      if (this.annotate()) {
        this.modules.annotate.init();
      }

      svg.append('defs').append('clipPath')
        .attr('id', _clipId)
        .append('rect')
          .attr('width', w)
          .attr('height', h);
    } else {
      this.wrapper.select('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom);

      svg.attr('transform', 'translate(' + m.left + ',' + m.top + ')');

      svg.select('#' + _clipId + ' rect')
        .attr('width', w)
        .attr('height', h);
    }

    if (svg.select('.x.axis').node()) {
      if (this.transition()) {
        svg.select('.x.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(0,' + h + ')')
            .call(xAxis);
      } else {
        svg.select('.x.axis')
          .attr('transform', 'translate(0,' + h + ')')
          .call(xAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + h + ')')
        .call(xAxis);
    }

    if (svg.select('.y.axis').node()) {
      if (this.transition()) {
        svg.select('.y.axis')
          .transition().duration(this.duration())
            .call(yAxis);
      } else {
        svg.select('.y.axis').call(yAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'y axis')
        .call(yAxis);
        // .append('text')
        //     .attr('transform', 'rotate(-90)')
        //     .attr('y', 6)
        //     .attr('dy', '.71em')
        //     .style('text-anchor', 'end')
        //     .text('Price ($)'); // TODO
    }

    series = svg.selectAll('.series')
      .data(chartData, this.seriesFormat());

    series
      .enter().append('g')
        .attr('class', 'series')
        .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); })
        .on('click', function(d, i) {
          self.dispatch.click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.dblclick(d, i);
        })
        .on('mouseover', function(d, i) {
          self.dispatch.mouseover(d, i);
        })
        .on('mouseout', function(d, i) {
          self.dispatch.mouseout(d, i);
        });

    series.attr('clip-path', 'url(#' + _clipId + ')');

    series.exit().remove();

    paths = series.selectAll('.area')
      .data(function(d) { return [d.values]; });

    paths
      .enter().append('path')
        .attr('class', 'area')
        .attr('d', emptyArea);

    paths.exit().remove();

    if (this.transition()) {
      paths
        .transition().duration(this.duration())
          .attr('d', area);
    } else {
      paths
        .attr('d', area);
    }

    series
      .on('mouseover', function(d, i) {
        rsc.interact.mouseover(
          series,
          this,
          null,
          self.tooltips() ? {
            wrapper: self.wrapper,
            text: '<h3>' + self.seriesFormat()(d) + '</h3>'
          } : null
        );

        self.dispatch.mouseover(d, i);
      })
      .on('mouseout', function(d, i) {
        rsc.interact.mouseout(series, self.tooltips() ? self.wrapper : null);

        self.dispatch.mouseout(d, i);
      })
      .on('mousemove', function(d, i) {
        if (self.tooltips()) {
          rsc.interact.mousemove(self.wrapper);
        }

        self.dispatch.mousemove(d, i);
      });

    if (this.legend()) {
      this.modules.legend.update();
    }

    return this;
  };

  return chart;
};
rsc.charts.bar = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove', 'legend_click', 'legend_dblclick');

  var _stacked = false;
  var _expanded = false;

  chart.stacked = function(stacked) {
    if (typeof stacked !== 'undefined') {
      _stacked = stacked;

      return this;
    } else {
      return _stacked;
    }
  };

  chart.expanded = function(expanded) {
    if (typeof expanded !== 'undefined') {
      _expanded = expanded;

      return this;
    } else {
      return _expanded;
    }
  };

  chart.render = function(update) {
    var x, y, xAxis, yAxis, svg, chartData, series, bars, h, w, m,
      self = this;

    if (this.legend()) {
      this.modules.legend.render(this.wrapper);
    } else {
      this.modules.legend.remove();
    }

    h = this.getChartHeight();
    w = this.getChartWidth();
    m = this.getChartMargin();

    x = d3.scale.ordinal()
      .rangeRoundBands([0, w], 0.1);

    y = d3.scale.linear()
      .range([h, 0]);

    xAxis = d3.svg.axis()
      .scale(x)
      .orient('bottom');

    yAxis = d3.svg.axis()
      .scale(y)
      .orient('left');

    if (this.expanded()) {
      yAxis.tickFormat(function(v) { return (v * 100) + '%'; });
    } else if (this.yTickFormat()) {
      yAxis.tickFormat(this.yTickFormat());
    } else {
      yAxis.tickFormat(rsc.utils.unitSuffixFormat);
    }

    if (this.grid()) {
      xAxis.tickSize(-h);
      yAxis.tickSize(-w);
    }

    svg = this.wrapper.select('.rsc-inner-wrapper');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom)
        .append('g')
          .attr('class', 'rsc-inner-wrapper')
          .attr('transform', 'translate(' + m.left + ',' + m.top + ')');
    } else {
      this.wrapper.select('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom);

      svg.attr('transform', 'translate(' + m.left + ',' + m.top + ')');
    }

    if (this.stacked() || this.expanded()) {
      var stack = d3.layout.stack()
        .values(function(d) { return d.values; })
        .x(self.x())
        .y(self.y())
        .offset(this.expanded() ? 'expand' : 'zero');

      chartData = stack(this.data().filter(function(d) { return !d.disabled; }));
    } else {
      chartData = this.data().filter(function(d) { return !d.disabled; });
    }

    chartData = chartData.map(function(series, i) {
      series.values = series.values.map(function(point) {
        point.series = i;
        return point;
      });
      return series;
    });

    x.domain(chartData[0].values.map(this.x())); // TODO: Using the first element is a hack

    if (this.expanded()) {
      y.domain([0, 1]);
    } else {
      y.domain([
        // d3.min(chartData, function(s) { return d3.min(s.values, self.y()); }),
        0,
        d3.max(chartData, function(s) {
          return self.stacked() ? d3.max(s.values, function(d) { return d.y0 + d.y; }) : d3.max(s.values, self.y());
        })
      ]);
    }

    if (svg.select('.x.axis').node()) {
      if (this.transition()) {
        svg.select('.x.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(0,' + h + ')')
            .call(xAxis);
      } else {
        svg.select('.x.axis')
          .attr('transform', 'translate(0,' + h + ')')
          .call(xAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + h + ')')
        .call(xAxis);
    }

    if (svg.select('.y.axis').node()) {
       if (this.transition()) {
        svg.select('.y.axis')
          .transition().duration(this.duration())
            .call(yAxis);
      } else {
        svg.select('.y.axis').call(yAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'y axis')
        .call(yAxis);
        // .append('text')
        //     .attr('transform', 'rotate(-90)')
        //     .attr('y', 6)
        //     .attr('dy', '.71em')
        //     .style('text-anchor', 'end')
        //     .text('Frequency'); // TODO
    }

    series = svg.selectAll('.series')
      .data(chartData, function(d) { return d.key; });

    series
      .enter().append('g')
        .attr('class', 'series')
        .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(d.key)); });

    series.exit().remove();

    bars = series.selectAll('.bar')
      .data(function(d) { return d.values; });

    bars
      .enter().append('rect')
        .attr('class', 'bar')
        .attr('y', h)
        .attr('height', 0)
        .on('click', function(d, i) {
          self.dispatch.click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.dblclick(d, i);
        });

    bars
      .attr('x', this.stacked() || this.expanded() ? function(d) { return x(self.x()(d)); } : function(d, i, j) { return x(self.x()(d)) + x.rangeBand() / chartData.length * j; })
      .attr('width', this.stacked() || this.expanded() ? x.rangeBand() : x.rangeBand() / chartData.length);

    bars.exit().remove();

    if (this.transition()) {
      bars
        .transition().duration(this.duration())
          .attr('y', this.stacked() || this.expanded() ? function(d) { return y(d.y0 + d.y); } : function(d) { return y(self.y()(d)); })
          .attr('height', this.stacked() || this.expanded() ? function(d) { return y(d.y0) - y(d.y0 + d.y); } : function(d) { return h - y(self.y()(d)); });
    } else {
      bars
        .attr('y', this.stacked() || this.expanded() ? function(d) { return y(d.y0 + d.y); } : function(d) { return y(self.y()(d)); })
        .attr('height', this.stacked() || this.expanded() ? function(d) { return y(d.y0) - y(d.y0 + d.y); } : function(d) { return h - y(self.y()(d)); });
    }

    bars
      .on('mouseover', function(d, i) {
        rsc.interact.mouseover(
          series,
          this.parentNode,
          function(currentNode) {
            return d3.select(currentNode).selectAll('.bar');
          },
          self.tooltips() ? {
            wrapper: self.wrapper,
            text: '<h3>' + self.x()(d) + ' - ' + chartData[d.series].key +
              '</h3><p>' + (self.yFormat() ? self.yFormat()(self.y()(d)) : d3.format(',.0f')(self.y()(d))) + '</p>' +
              (self.expanded() ? '<p>' + d3.format('%')(d.y) + '</p>' : '')
          } : null
        );

        self.dispatch.mouseover(d, i);
      })
      .on('mouseout', function(d, i) {
        rsc.interact.mouseout(bars, self.tooltips() ? self.wrapper : null);

        self.dispatch.mouseout(d, i);
      })
      .on('mousemove', function(d, i) {
        if (self.tooltips()) {
          rsc.interact.mousemove(self.wrapper);
        }

        self.dispatch.mousemove(d, i);
      });

    if (this.legend()) {
      this.modules.legend.update();
    }

    return this;
  };

  return chart;
};
rsc.charts.discreteBar = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove');

  chart.render = function(update) {
    var x, y, xAxis, yAxis, svg, bars,
      self = this;

    x = d3.scale.ordinal()
      .rangeRoundBands([0, this.width()], 0.1);

    y = d3.scale.linear()
      .range([this.height(), 0]);

    xAxis = d3.svg.axis()
      .scale(x)
      .orient('bottom');

    yAxis = d3.svg.axis()
      .scale(y)
      .orient('left');

    if (this.yTickFormat()) {
      yAxis.tickFormat(this.yTickFormat());
    } else {
      yAxis.tickFormat(rsc.utils.unitSuffixFormat);
    }

    if (this.grid()) {
      xAxis.tickSize(-this.height());
      yAxis.tickSize(-this.width());
    }

    x.domain(this.data().map(this.x()));
    y.domain([0, d3.max(this.data(), this.y())]);

    svg = this.wrapper.select('.rsc-inner-wrapper');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('width', this.width() + this.margin().left + this.margin().right)
        .attr('height', this.height() + this.margin().top + this.margin().bottom)
        .append('g')
          .attr('class', 'rsc-inner-wrapper')
          .attr('transform', 'translate(' + this.margin().left + ',' + this.margin().top + ')');
    } else {
      this.wrapper.select('svg')
        .attr('width', this.width() + this.margin().left + this.margin().right)
        .attr('height', this.height() + this.margin().top + this.margin().bottom);

      svg.attr('transform', 'translate(' + this.margin().left + ',' + this.margin().top + ')');
    }

    if (svg.select('.x.axis').node()) {
      if (this.transition()) {
        svg.select('.x.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(0,' + this.height() + ')')
            .call(xAxis);
      } else {
        svg.select('.x.axis')
          .attr('transform', 'translate(0,' + this.height() + ')')
          .call(xAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + this.height() + ')')
        .call(xAxis);
    }

    if (svg.select('.y.axis').node()) {
      if (this.transition()) {
        svg.select('.y.axis')
          .transition().duration(this.duration())
            .call(yAxis);
      } else {
        svg.select('.y.axis').call(yAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'y axis')
        .call(yAxis);
        // .append('text')
        //     .attr('transform', 'rotate(-90)')
        //     .attr('y', 6)
        //     .attr('dy', '.71em')
        //     .style('text-anchor', 'end')
        //     .text('Frequency'); // TODO
    }

    bars = svg.selectAll('.bar')
      .data(this.data());

    bars
      .enter().append('rect')
        .attr('class', 'bar')
        .attr('y', this.height())
        .attr('height', 0)
        .on('click', function(d, i) {
          self.dispatch.click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.dblclick(d, i);
        });

    bars.exit().remove();

    bars
      .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.x()(d))); });

    if (this.transition() && update) {
      bars
        .transition().duration(this.duration())
          .attr('y', function(d) { return y(self.y()(d)); })
          .attr('height', function(d) { return self.height() - y(self.y()(d)); })
          .attr('x', function(d) { return x(self.x()(d)); })
          .attr('width', x.rangeBand());
    } else if (this.transition()) {
      bars
        .attr('x', function(d) { return x(self.x()(d)); })
        .attr('width', x.rangeBand())
        .transition().duration(this.duration())
          .attr('y', function(d) { return y(self.y()(d)); })
          .attr('height', function(d) { return self.height() - y(self.y()(d)); });
    } else {
      bars
        .attr('y', function(d) { return y(self.y()(d)); })
        .attr('height', function(d) { return self.height() - y(self.y()(d)); })
        .attr('x', function(d) { return x(self.x()(d)); })
        .attr('width', x.rangeBand());
    }

    bars
      .on('mouseover', function(d, i) {
        rsc.interact.mouseover(
          bars,
          this,
          null,
          self.tooltips() ? {
            wrapper: self.wrapper,
            text: '<h3>' + self.x()(d) + '</h3><p>' + (self.yTickFormat() ? self.yTickFormat()(self.y()(d)) : d3.format(',.0f')(self.y()(d))) + '</p>'
          } : null
        );

        self.dispatch.mouseover(d, i);
      })
      .on('mouseout', function(d, i) {
        rsc.interact.mouseout(bars, self.tooltips() ? self.wrapper : null);

        self.dispatch.mouseout(d, i);
      })
      .on('mousemove', function(d, i) {
        if (self.tooltips()) {
          rsc.interact.mousemove(self.wrapper);
        }

        self.dispatch.mousemove(d, i);
      });

    return this;
  };

  return chart;
};
rsc.charts.line = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove',
    'path_click', 'path_dblclick', 'path_mouseover', 'path_mouseout', 'path_mousemove',
    'legend_click', 'legend_dblclick', 'annotate');

  var _clipId = 'clip_' + rsc.utils.generateUUID();
  var _baselineIndex;

  var _points = true;
  var _radius = 3;
  var _focus = false;
  var _index = false;
  var _seriesFormat = function(d) { return d.key; };
  var _annotate = false;

  chart.modules.annotate = new rsc.annotate(chart);

  chart.points = function(points) {
    if (typeof points !== 'undefined') {
      _points = points;

      return this;
    } else {
      return _points;
    }
  };

  chart.radius = function(radius) {
    if (typeof radius !== 'undefined') {
      _radius = radius;

      return this;
    } else {
      return _radius;
    }
  };

  chart.focus = function(focus) {
    if (typeof focus !== 'undefined') {
      _focus = focus;

      return this;
    } else {
      return _focus;
    }
  };

  chart.index = function(index) {
    if (typeof index !== 'undefined') {
      _index = index;

      return this;
    } else {
      return _index;
    }
  };

  chart.seriesFormat = function(seriesFormat) {
    if (typeof seriesFormat !== 'undefined') {
      if (seriesFormat === null) {
        _seriesFormat = function(d) { return d.key; };
      } else {
        _seriesFormat = seriesFormat;
      }

      return this;
    } else {
      return _seriesFormat;
    }
  };

  chart.annotate = function(annotate) {
    if (typeof annotate !== 'undefined') {
      _annotate = annotate;

      return this;
    } else {
      return _annotate;
    }
  };

  chart.drawAnnotation = function(annotationConfig) {
    if (!this.annotate()) return;

    this.modules.annotate.render(annotationConfig);
  };

  chart.xTickFormat(rsc.utils.multiTimeFormat);

  chart.render = function(update) {
    var _height1, _height2, x, x2, y, y2, xAxis, xAxis2, yAxis, yAxis2,
      brush, line, line2, svg, main, context, mainSeries, mainPaths,
      contextSeries, contextPaths, points, h, w, m, chartData, cutIndex,
      self = this;

    if (this.legend()) {
      this.modules.legend.key(this.seriesFormat());
      this.modules.legend.render(this.wrapper);
    } else {
      this.modules.legend.remove();
    }

    h = this.getChartHeight();
    w = this.getChartWidth();
    m = this.getChartMargin();

    if (this.focus()) {
      _height2 = h * 0.1;
      _height1 = h - _height2 - 10;
    } else {
      _height1 = h;
    }

    x = d3.time.scale()
      .range([0, w]);

    this._xScale = x;

    if (this.focus()) {
      x2 = d3.time.scale()
        .range([0, w]);
    }

    y = d3.scale.linear()
      .range([_height1, 0]);

    this._yScale = y;

    if (this.focus()) {
      y2 = d3.scale.linear()
        .range([_height2, 0]);
    }

    xAxis = d3.svg.axis()
      .scale(x)
      .orient('bottom');

    xAxis.tickFormat(this.xTickFormat());

    if(this.focus()) {
      xAxis2 = d3.svg.axis()
        .scale(x2)
        .orient('bottom');
    }

    yAxis = d3.svg.axis()
      .scale(y)
      .orient('left');

    if (this.index()) {
      yAxis.tickFormat(function(v) {
        var pct = d3.round(v * 100, 2);
        return (pct > 0 ? '+' : '') + pct + '%';
      });
    } else if (this.yTickFormat()) {
      yAxis.tickFormat(this.yTickFormat());
    } else {
      yAxis.tickFormat(rsc.utils.unitSuffixFormat);
    }

    if (this.focus()) {
      yAxis2 = d3.svg.axis()
        .scale(y2)
        .ticks(0)
        .orient('left');
    }

    if (this.grid()) {
      xAxis.tickSize(-_height1);
      yAxis.tickSize(-w);
    }

    if (this.focus()) {
      brush = d3.svg.brush()
        .x(x2)
        .on('brush', function() {
          x.domain(brush.empty() ? x2.domain() : brush.extent());
          mainPaths.attr('d', line);
          if (self.points()) {
            var mouseover, mouseout;
            if (self.tooltips()) {
              mouseover = points.on('mouseover');
              mouseout = points.on('mouseout');
            }

            points = mainSeries.selectAll('.point')
              .data(function(d) { return d.values; });

            points
              .enter().append('circle')
                .attr('class', 'point')
                .attr('r', self.radius());

            points
              .attr('cx', function(d) { return x(self.x()(d)); })
              .attr('cy', function(d) { return y(self.y()(d)); });

            points.exit().remove();

            if (self.tooltips()) {
              points
                .on('mouseover', mouseover)
                .on('mouseout', mouseout);
            }
          }
          main.select('.x.axis').call(xAxis);
        });
    }

    line = d3.svg.line()
      .defined(function(d) { return self.y()(d) !== null; })
      .x(function(d) { return x(self.x()(d)); })
      .y(function(d) { return y(self.y()(d)); })
      .interpolate('linear');

    if (this.focus()) {
      line2 = d3.svg.line()
        .defined(function(d) { return self.y()(d) !== null; })
        .x(function(d) { return x2(self.x()(d)); })
        .y(function(d) { return y2(self.y()(d)); })
        .interpolate('linear');
    }

    svg = this.wrapper.select('svg');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('class', 'rsc-canvas')
        .attr('width', w + m.left + m.right)
        .attr('height', _height1 + (this.focus() ? _height2 + 10 : 0) + m.top + m.bottom);

      if (this.annotate()) {
        this.modules.annotate.init();
      }

      main = svg.append('g')
        .attr('class', 'focus')
        .attr('transform', 'translate(' + m.left + ',' + m.top + ')');

      if (this.focus()) {
        svg.append('defs').append('clipPath')
          .attr('id', _clipId)
          .append('rect')
            .attr('width', w)
            .attr('height', _height1);

        context = svg.append('g')
          .attr('class', 'context')
          .attr('transform', 'translate(' + m.left + ',' +
            (m.bottom + _height1 + 10 - (this.legend() ? this.modules.legend.height - this.modules.legend.padding : 0)) + ')');
      }
    } else {
      svg
        .attr('width', w + m.left + m.right)
        .attr('height', _height1 + (this.focus() ? _height2 + 10 : 0) + m.top + m.bottom);

      svg.select('#' + _clipId + ' rect')
        .attr('width', w)
        .attr('height', _height1);

      main = svg.select('.focus')
        .attr('transform', 'translate(' + m.left + ',' + m.top + ')');

      if (this.focus()) {
        context = svg.select('.context')
          .attr('transform', 'translate(' + m.left + ',' +
            (m.bottom + _height1 + 10 - (this.legend() ? this.modules.legend.height - this.modules.legend.padding : 0)) + ')');
      }
    }

    if (typeof update === 'undefined' || update === null || update === false) {
      _baselineIndex = null;
    }

    chartData = this.data().filter(function(d) { return !d.disabled; });

    function getAllowedIndex(idx, field) {
      var k;
      if (typeof idx === 'undefined' || idx === null) {
        idx = 0;
      }

      for (k = idx; k < chartData[0].values.length; k++) {
        if ((field ? chartData[0].values[k][field] : self.y()(chartData[0].values[k])) === 0) {
          continue;
        } else {
          var found = false;
          for (var n = 1; n < chartData.length; n++) {
            if ((field ? chartData[n].values[k][field] : self.y()(chartData[n].values[k])) === 0) {
              found = true;
              break;
            }
          }
          if (!found) {
            break;
          }
        }
      }
      return k;
    }

    cutIndex = 0;

    if (this.index()) {
      if (typeof _baselineIndex === 'undefined' || _baselineIndex === null) {
        cutIndex = getAllowedIndex();
      }
    }

    chartData.map(function(series, i) {
      var baseline, yStr, yField;
      if (self.index()) {
        if (typeof _baselineIndex === 'undefined' || _baselineIndex === null || _baselineIndex < cutIndex) {
          _baselineIndex = 0;
        } else {
          _baselineIndex = getAllowedIndex(_baselineIndex, '_originalY');
        }

        series.values = series.values.slice(cutIndex);

        baseline = (typeof series.values[_baselineIndex]._originalY === 'undefined' || series.values[_baselineIndex]._originalY === null) ?
          self.y()(series.values[_baselineIndex]) : series.values[_baselineIndex]._originalY;
        yStr = self.y().toString();
        yField = yStr.substring(yStr.indexOf('.') + 1, yStr.indexOf(';'));
      }

      series.values = series.values.map(function(point, idx) {
        if (self.index()) {
          if (typeof point._originalY === 'undefined' || point._originalY === null) {
            point._originalY = self.y()(point);
          }
          point[yField] = (point._originalY / baseline * 100 - 100) / 100;
        }
        point.series = i;
        return point;
      });

      return series;
    });

    x.domain([
      d3.min(chartData, function(s) { return d3.min(s.values, self.x()); }),
      d3.max(chartData, function(s) { return d3.max(s.values, self.x()); })
    ]);
    y.domain([
      d3.min(chartData, function(s) { return d3.min(s.values, self.y()); }),
      d3.max(chartData, function(s) { return d3.max(s.values, self.y()); })
    ]);

    if (this.focus()) {
      x2.domain(x.domain());
      y2.domain(y.domain());
    }

    if (main.select('.x.axis').node()) {
      if (this.transition()) {
        main.selectAll('.x.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(0,' + _height1 + ')')
            .call(xAxis);
      } else {
        main.select('.x.axis')
          .attr('transform', 'translate(0,' + _height1 + ')')
          .call(xAxis);
      }
    } else {
      main.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + _height1 + ')')
        .call(xAxis);
    }

    if (this.focus()) {
      if (context.select('.x.axis').node()) {
        if (this.transition()) {
          context.selectAll('.x.axis')
            .transition().duration(this.duration())
              .attr('transform', 'translate(0,' + _height2 + ')')
              .call(xAxis2);
        } else {
          context.select('.x.axis')
            .attr('transform', 'translate(0,' + _height2 + ')')
            .call(xAxis2);
        }
      } else {
        context.append('g')
          .attr('class', 'x axis')
          .attr('transform', 'translate(0,' + _height2 + ')')
          .call(xAxis2);
      }
    }

    if (main.select('.y.axis').node()) {
      if (this.transition()) {
        main.select('.y.axis')
          .transition().duration(this.duration())
            .call(yAxis);
      } else {
        main.select('.y.axis').call(yAxis);
      }
    } else {
      main.append('g')
        .attr('class', 'y axis')
        .call(yAxis);
        // .append('text')
        //     .attr('transform', 'rotate(-90)')
        //     .attr('y', 6)
        //     .attr('dy', '.71em')
        //     .style('text-anchor', 'end')
        //     .text('Price ($)'); // TODO
    }

    if (this.focus()) {
      if (context.select('.y.axis').node()) {
        if (this.transition()) {
          context.select('.y.axis')
            .transition().duration(this.duration())
              .call(yAxis2);
        } else {
          context.select('.y.axis').call(yAxis2);
        }
      } else {
        context.append('g')
          .attr('class', 'y axis')
          .call(yAxis2);
      }
    }

    if (this.index()) {
      var dragIndexLine = d3.behavior.drag()
        .on('dragstart', function() {
          d3.event.sourceEvent.stopPropagation();
        })
        .on('drag', function(d, i) {
          var node = d3.select(this);
          var x1 = Math.max(0, Math.min(w, d3.event.x));

          var min;
          var closestX;
          var closestIndex;
          main.select('.series').selectAll('.point').each(function(d, idx) {
            if (d._originalY === 0) return;

            var curX = x(self.x()(d));
            var diff = Math.abs(x1 - curX);

            if (typeof min === 'undefined' || min === null) {
              min = diff;
              closestX = curX;
              closestIndex = idx;
            } else if (diff < min) {
              min = diff;
              closestX = curX;
              closestIndex = idx;
            }
          });

          node
            .attr('x1', closestX)
            .attr('x2', closestX);

          if (self.focus()) {
            context.select('.index-line')
              .attr('x1', closestX)
              .attr('x2', closestX);
          }

          if (closestIndex !== _baselineIndex) {
            _baselineIndex = closestIndex;
            self.update();
          }
        });

      if (main.select('.index-line').node()) {
        var baselineX = x(this.x()(chartData[0].values[_baselineIndex]));

        main.select('.index-label').remove();

        if (this.transition()) {
          main.select('.index-line')
            .transition().duration(this.duration())
              .attr('x1', baselineX)
              .attr('x2', baselineX);

          if (this.focus()) {
            context.select('.index-line')
              .transition().duration(this.duration())
                .attr('x1', baselineX)
                .attr('x2', baselineX);
          }
        } else {
          main.select('.index-line')
            .attr('x1', baselineX)
            .attr('x2', baselineX);

          if (this.focus()) {
            context.select('.index-line')
              .attr('x1', baselineX)
              .attr('x2', baselineX);
          }
        }
      } else {
        var indexLineWrapper = main.append('g');

        indexLineWrapper.append('line')
          .attr('class', 'index-line')
          .attr('y1', _height1)
          .call(dragIndexLine);

        indexLineWrapper.append('text')
          .attr('class', 'index-label')
          .attr('x', 5)
          .attr('y', 6)
          .attr('dy', '.71em')
          .text('<- Drag Index Line');

        main.select('.index-line')
          .on('mouseover', function(d, i) {
            var node = d3.select(this);
            rsc.tooltip.show(
              d3.event.pageX,
              d3.event.pageY,
              self.wrapper,
              '<h3>' + (self.xFormat() ? self.xFormat()(self.x()(chartData[0].values[_baselineIndex])) :
                rsc.utils.timeFormat(self.x()(chartData[0].values[_baselineIndex]))) + '</h3>'
            );
          })
          .on('mouseout', function(d, i) {
            rsc.tooltip.remove(self.wrapper);
          });

        if (this.focus()) {
          context.append('line')
            .attr('class', 'index-line')
            .attr('y1', _height2);
        }
      }
    }

    mainSeries = main.selectAll('.series')
      .data(chartData, this.seriesFormat());

    mainSeries
      .enter().append('g')
        .attr('class', 'series')
        .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); })
        .attr('stroke', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); });

    if (this.focus()) {
      mainSeries.attr('clip-path', 'url(#' + _clipId + ')');
    }

    mainSeries.exit().remove();

    mainPaths = mainSeries.selectAll('.line')
      .data(function(d) { return [d.values]; });

    mainPaths
      .enter().append('path')
      .attr('class', 'line');

    mainPaths.exit().remove();

    if(!update || (update && !this.transition())) {
      mainPaths.attr('d', line);
    }

    if (this.focus()) {
      contextSeries = context.selectAll('.series')
        .data(chartData, this.seriesFormat());

      contextSeries
        .enter().append('g')
          .attr('class', 'series')
          .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); })
          .attr('stroke', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); });

      contextSeries.exit().remove();

      contextPaths = contextSeries.selectAll('.line')
        .data(function(d) { return [d.values]; });

      contextPaths
        .enter().append('path')
        .attr('class', 'line');

      contextPaths.exit().remove();

      if(!update || (update && !this.transition())) {
        contextPaths.attr('d', line2);
      }

      if (context.select('.x.brush').node()) {
        context.select('.x.brush').remove();
      }

      context.append('g')
        .attr('class', 'x brush')
        .call(brush)
        .selectAll('rect')
          .attr('y', -6)
          .attr('height', _height2 + 7);
    }

    if (this.points()) {
      points = mainSeries.selectAll('.point')
        .data(function(d) { return d.values; });

      points
        .enter().append('circle')
          .attr('class', 'point')
          .attr('r', this.radius())
          .on('click', function(d, i) {
            self.dispatch.click(d, i);
          })
          .on('dblclick', function(d, i) {
            self.dispatch.dblclick(d, i);
          });

      if (!update || (update && !this.transition())) {
        points
          .attr('cx', function(d) { return x(self.x()(d)); })
          .attr('cy', function(d) { return y(self.y()(d)); });
      }

      points.exit().remove();

      if (this.transition() && !update) points.attr('opacity', 0);

      points
        .on('mouseover', function(d, i) {
          rsc.interact.mouseover(
            mainSeries.selectAll('.line'),
            d3.select(this.parentNode).select('.line').node(),
            function(currentNode) {
              return d3.select(currentNode.parentNode).selectAll('.line, .point');
            },
            self.tooltips() ? {
              wrapper: self.wrapper,
              text: '<h3>' + (self.xFormat() ? self.xFormat()(self.x()(d)) : rsc.utils.timeFormat(self.x()(d))) +
                (chartData.length > 1 ? ' - ' + self.seriesFormat()(chartData[d.series]) : '') +
                '</h3><p>' + (self.index() ? yAxis.tickFormat()(self.y()(d)) : (self.yFormat() ? self.yFormat()(self.y()(d)) : d3.format(',.0f')(self.y()(d)))) + '</p>' +
                (self.index() ? '<p>' + d3.format(',.0f')(d._originalY) + '</p>' : '')
            } : null
          );

          self.dispatch.mouseover(d, i);
        })
        .on('mouseout', function(d, i) {
          rsc.interact.mouseout(mainSeries.selectAll('.line, .point'), self.tooltips() ? self.wrapper : null);

          self.dispatch.mouseout(d, i);
        })
        .on('mousemove', function(d, i) {
          if (self.tooltips()) {
            rsc.interact.mousemove(self.wrapper);
          }

          self.dispatch.mousemove(d, i);
        });

      mainSeries.selectAll('.line')
        .on('mouseover', function(d, i) {
          rsc.interact.mouseover(
            mainSeries.selectAll('.line'),
            this,
            function(currentNode) {
              return d3.select(currentNode.parentNode).selectAll('.line, .point');
            },
            self.tooltips() ? {
              wrapper: self.wrapper,
              text: '<h3>' + (Object.prototype.toString.call(d) !== '[object Array]' ? self.seriesFormat()(d) : self.seriesFormat()(chartData[d[0].series])) + '</h3>'
            } : null
          );

          self.dispatch.path_mouseover(d, i);
        })
        .on('mouseout', function(d, i) {
          rsc.interact.mouseout(mainSeries.selectAll('.line, .point'), self.tooltips() ? self.wrapper : null);

          self.dispatch.path_mouseout(d, i);
        })
        .on('mousemove', function(d, i) {
          if (self.tooltips()) {
            rsc.interact.mousemove(self.wrapper);
          }

          self.dispatch.path_mousemove(d, i);
        })
        .on('click', function(d, i) {
          self.dispatch.path_click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.path_dblclick(d, i);
        });
    } else {
      mainSeries.selectAll('.line')
        .on('mouseover', function(d, i) {
          rsc.interact.mouseover(
            mainSeries.selectAll('.line'),
            this,
            function(currentNode) {
              return d3.select(currentNode.parentNode).selectAll('.line');
            },
            self.tooltips() ? {
              wrapper: self.wrapper,
              text: '<h3>' + (Object.prototype.toString.call(d) !== '[object Array]' ? self.seriesFormat()(d) : self.seriesFormat()(chartData[d[0].series])) + '</h3>'
            } : null
          );

          self.dispatch.path_mouseover(d, i);
        })
        .on('mouseout', function(d, i) {
          rsc.interact.mouseout(mainSeries.selectAll('.line'), self.tooltips() ? self.wrapper : null);

          self.dispatch.path_mouseout(d, i);
        })
        .on('mousemove', function(d, i) {
          self.dispatch.path_mousemove(d, i);
        })
        .on('click', function(d, i) {
          self.dispatch.path_click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.path_dblclick(d, i);
        });
    }

    if (this.transition()) {
      mainSeries.selectAll('.line').each(function(d, i) {
        var node = d3.select(this);
        if (node.attr('d') === null || !update) {
          node.attr('d', line);
          var pathLength = node.node().getTotalLength();
          node
            .attr('stroke-dasharray', pathLength + ' ' + pathLength)
            .attr('stroke-dashoffset', pathLength)
            .transition().duration(self.duration())
              .attr('stroke-dashoffset', 0)
              .each('end', function() {
                d3.select(this).attr('stroke-dasharray', '');
              });
        } else {
          node
            .transition().duration(self.duration())
              .attr('d', line);
        }
      });

      if (this.focus()) {
        contextSeries.selectAll('.line').each(function(d, i) {
          var node = d3.select(this);
          if (node.attr('d') === null || !update) {
            node.attr('d', line2);
            var pathLength = node.node().getTotalLength();
            node
              .attr('stroke-dasharray', pathLength + ' ' + pathLength)
              .attr('stroke-dashoffset', pathLength)
              .transition().duration(self.duration())
                .attr('stroke-dashoffset', 0)
                .each('end', function() {
                  d3.select(this).attr('stroke-dasharray', '');
                });
          } else {
            node
              .transition().duration(self.duration())
                .attr('d', line2);
          }
        });
      }

      if (this.points()) {
        svg.selectAll('.point').each(function(d, i) {
          var node = d3.select(this);
          if (node.attr('opacity') === '0' || node.attr('cx') === null) {
            node
              .attr('opacity', 0)
              .attr('cx', function(d) { return x(self.x()(d)); })
              .attr('cy', function(d) { return y(self.y()(d)); })
              .transition().duration(self.duration())
                .attr('opacity', 1);
          } else {
            node
              .transition().duration(self.duration())
                .attr('cx', function(d) { return x(self.x()(d)); })
                .attr('cy', function(d) { return y(self.y()(d)); });
          }
        });
      }
    }

    if (this.legend()) {
      this.modules.legend.update();
    }

    return this;
  };

  return chart;
};
rsc.charts.pie = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove', 'legend_click', 'legend_dblclick');

  var LABEL_THRESHOLD = 0.02;

  var _donut = false;

  chart.donut = function(donut) {
    if (typeof donut !== 'undefined') {
      _donut = donut;

      return this;
    } else {
      return _donut;
    }
  };

  chart.render = function(update) {
    var radius, arc, pie, svg, slices, g, h, w, m, total, chartData,
      self = this;

    if (this.legend()) {
      this.modules.legend.key(this.x());
      this.modules.legend.render(this.wrapper);
    }

    h = this.getChartHeight();
    w = this.getChartWidth();
    m = this.getChartMargin();

    radius = Math.min(w + m.left + m.right, h + m.top + m.bottom) / 2;

    arc = d3.svg.arc()
      .outerRadius(radius - 10)
      .innerRadius(this.donut() ? radius / 2 : 0);

    pie = d3.layout.pie()
      .sort(null)
      .value(self.y());

    svg = this.wrapper.select('.rsc-inner-wrapper');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom)
        .append('g')
          .attr('class', 'rsc-inner-wrapper')
          .attr('transform', 'translate(' + ((w + m.left + m.right) / 2) + ',' + ((h + m.top + m.bottom) / 2) + ')');
    } else {
      this.wrapper.select('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom);

      svg.attr('transform', 'translate(' + ((w + m.left + m.right) / 2) + ',' + ((h + m.top + m.bottom) / 2) + ')');
    }

    chartData = this.data().filter(function(d) { return !d.disabled; });

    total = d3.sum(chartData, self.y());

    chartData.map(function(d, i) {
      d.internal_percentShare = d3.round(self.y()(d) / total * 100, 2);
      return d;
    });

    slices = svg.selectAll('.slice')
      .data(pie(chartData), function(d) { return self.x()(d.data); });

    g = slices
      .enter().append('g')
        .attr('class', 'slice')
        .on('click', function(d, i) {
          self.dispatch.click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.dblclick(d, i);
        });

    slices.exit().remove();

    g.append('path')
      .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.x()(d.data))); })
      .each(function(d) { this._current = d; });

    if (!this.legend()) {
      g.append('text')
        .attr('transform', 0)
        .attr('dy', '.35em')
        .style('text-anchor', 'middle');

      slices.select('text')
        .text(function(d) {
          var pct = (d.endAngle - d.startAngle) / (2 * Math.PI);
          return (self.x()(d.data) && pct > LABEL_THRESHOLD) ? self.x()(d.data) : '';
        });
    }

    function arcTween(a) {
      var i = d3.interpolate(update ? this._current : { startAngle: 0, endAngle: 0 }, a);
      this._current = i(0);
      return function(t) {
        return arc(i(t));
      };
    }

    if (this.transition()) {
      slices.select('path')
        .transition().duration(this.duration())
          .attr('d', arc)
          .attrTween('d', arcTween);

      if (!this.legend()) {
        slices.select('text')
          .transition().duration(this.duration())
            .attr('transform', function(d) { return 'translate(' + arc.centroid(d) + ')'; });
      }
    } else {
      slices.select('path')
        .attr('d', arc);

      if (!this.legend()) {
        slices.select('text')
          .attr('transform', function(d) { return 'translate(' + arc.centroid(d) + ')'; });
      }
    }

    slices
      .on('mouseover', function(d, i) {
        rsc.interact.mouseover(
          slices.selectAll('path'),
          d3.select(this).select('path').node(),
          null,
          self.tooltips() ? {
            wrapper: self.wrapper,
            text: '<h3>' + self.x()(d.data) + '</h3><p>' + (self.yFormat() ? self.yFormat()(self.y()(d.data)) : d3.format(',.0f')(self.y()(d.data))) + '</p>' +
              '<p>' + (d.data.internal_percentShare + '%') + '</p>'
          } : null
        );

        self.dispatch.mouseover(d, i);
      })
      .on('mouseout', function(d, i) {
        rsc.interact.mouseout(slices.selectAll('path'), self.tooltips() ? self.wrapper : null);

        self.dispatch.mouseout(d, i);
      })
      .on('mousemove', function(d, i) {
        if (self.tooltips()) {
          rsc.interact.mousemove(self.wrapper);
        }

        self.dispatch.mousemove(d, i);
      });

    if (this.legend()) {
      this.modules.legend.update();
    }

    return this;
  };

  return chart;
};
rsc.charts.scatter = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove', 'legend_click', 'legend_dblclick', 'annotate');

  var _radius = 3;
  var _seriesFormat = function(d) { return d.key; };
  var _annotate = false;

  chart.modules.annotate = new rsc.annotate(chart);

  chart.radius = function(radius) {
    if (typeof radius !== 'undefined') {
      _radius = radius;

      return this;
    } else {
      return _radius;
    }
  };

  chart.seriesFormat = function(seriesFormat) {
    if (typeof seriesFormat !== 'undefined') {
      if (seriesFormat === null) {
        _seriesFormat = function(d) { return d.key; };
      } else {
        _seriesFormat = seriesFormat;
      }

      return this;
    } else {
      return _seriesFormat;
    }
  };

  chart.annotate = function(annotate) {
    if (typeof annotate !== 'undefined') {
      _annotate = annotate;

      return this;
    } else {
      return _annotate;
    }
  };

  chart.drawAnnotation = function(annotationConfig) {
    if (!this.annotate()) return;

    this.modules.annotate.render(annotationConfig);
  };

  chart.render = function(update) {
    var x, y, xAxis, yAxis, svg, series, points, h, w, m, chartData,
      self = this;

    if (this.legend()) {
      this.modules.legend.key(this.seriesFormat());
      this.modules.legend.render(this.wrapper);
    } else {
      this.modules.legend.remove();
    }

    h = this.getChartHeight();
    w = this.getChartWidth();
    m = this.getChartMargin();

    x = d3.scale.linear()
      .range([0, w]);

    this._xScale = x;

    y = d3.scale.linear()
      .range([h, 0]);

    this._yScale = y;

    xAxis = d3.svg.axis()
      .scale(x)
      .orient('bottom');

    if (this.xTickFormat()) {
      xAxis.tickFormat(this.xTickFormat());
    }

    yAxis = d3.svg.axis()
      .scale(y)
      .orient('left');

    if (this.yTickFormat()) {
      yAxis.tickFormat(this.yTickFormat());
    } else {
      yAxis.tickFormat(rsc.utils.unitSuffixFormat);
    }

    if (this.grid()) {
      xAxis.tickSize(-h);
      yAxis.tickSize(-w);
    }

    svg = this.wrapper.select('.rsc-inner-wrapper');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('class', 'rsc-canvas')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom)
        .append('g')
          .attr('class', 'rsc-inner-wrapper')
          .attr('transform', 'translate(' + m.left + ',' + m.top + ')');

      if (this.annotate()) {
        this.modules.annotate.init();
      }
    } else {
      this.wrapper.select('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom);

      svg.attr('transform', 'translate(' + m.left + ',' + m.top + ')');
    }

    chartData = this.data().filter(function(d) { return !d.disabled; })
      .map(function(series, i) {
        series.values = series.values.map(function(point) {
          point.series = i;
          return point;
        });
        return series;
      });

    x.domain([
      d3.min(chartData, function(s) { return d3.min(s.values, self.x()); }),
      d3.max(chartData, function(s) { return d3.max(s.values, self.x()); })
    ]);
    y.domain([
      d3.min(chartData, function(s) { return d3.min(s.values, self.y()); }),
      d3.max(chartData, function(s) { return d3.max(s.values, self.y()); })
    ]);

    if (svg.select('.x.axis').node()) {
      if (this.transition()) {
        svg.select('.x.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(0,' + h + ')')
            .call(xAxis);
      } else {
        svg.select('.x.axis')
          .attr('transform', 'translate(0,' + h + ')')
          .call(xAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + h + ')')
        .call(xAxis);
    }

    if (svg.select('.y.axis').node()) {
      if (this.transition()) {
        svg.select('.y.axis')
          .transition().duration(this.duration())
            .call(yAxis);
      } else {
        svg.select('.y.axis').call(yAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'y axis')
        .call(yAxis);
        // .append('text')
        //     .attr('transform', 'rotate(-90)')
        //     .attr('y', 6)
        //     .attr('dy', '.71em')
        //     .style('text-anchor', 'end')
        //     .text('Price ($)'); // TODO
    }

    series = svg.selectAll('.series')
      .data(chartData, this.seriesFormat());

    series
      .enter().append('g')
        .attr('class', 'series')
        .attr('fill', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); })
        .attr('stroke', function(d, i) { return self.color()(rsc.utils.stringToHashCode(self.seriesFormat()(d))); });

    series.exit().remove();

    points = series.selectAll('.point')
      .data(function(d) { return d.values; });

    points
      .enter().append('circle')
        .attr('class', 'point')
        .attr('r', this.radius())
        .on('click', function(d, i) {
          self.dispatch.click(d, i);
        })
        .on('dblclick', function(d, i) {
          self.dispatch.dblclick(d, i);
        });

    if (!update || (update && !this.transition())) {
      points
        .attr('cx', function(d) { return x(self.x()(d)); })
        .attr('cy', function(d) { return y(self.y()(d)); });
    }

    points.exit().remove();

    if (this.transition()) {
      if (update) {
        points
          .transition().duration(this.duration())
            .attr('cx', function(d) { return x(self.x()(d)); })
            .attr('cy', function(d) { return y(self.y()(d)); });
      } else {
        points
          .style('opacity', 0)
          .transition().duration(this.duration())
            .style('opacity', 1);
      }
    }

    points
      .on('mouseover', function(d, i) {
        rsc.interact.mouseover(
          series,
          this.parentNode,
          function(currentNode) {
            return d3.select(currentNode).selectAll('.point');
          },
          self.tooltips() ? {
            wrapper: self.wrapper,
            text: '<h3>' + (self.xFormat() ? self.xFormat()(self.x()(d)) : self.x()(d)) +
              (chartData.length > 1 ? ' - ' + self.seriesFormat()(chartData[d.series]) : '') +
              '</h3><p>' + (self.yFormat() ? self.yFormat()(self.y()(d)) : d3.format(',.0f')(self.y()(d))) + '</p>'
          } : null
        );

        self.dispatch.mouseover(d, i);
      })
      .on('mouseout', function(d, i) {
        rsc.interact.mouseout(points, self.tooltips() ? self.wrapper : null);

        self.dispatch.mouseout(d, i);
      })
      .on('mousemove', function(d, i) {
        if (self.tooltips()) {
          rsc.interact.mousemove(self.wrapper);
        }

        self.dispatch.mousemove(d, i);
      });

    if (this.legend()) {
      this.modules.legend.update();
    }

    return this;
  };

  return chart;
};
rsc.charts.heatmap = function(parent) {
  var chart = new this.base(parent);

  chart.dispatch = d3.dispatch('click', 'dblclick', 'mouseover', 'mouseout', 'mousemove', 'legend_click', 'legend_dblclick');

  var THEME_MAPPINGS = {
    'light': 'white',
    'dark': 'black'
  };

  var _seriesFormat = function(d) { return d.key; };

  chart.seriesFormat = function(seriesFormat) {
    if (typeof seriesFormat !== 'undefined') {
      if (seriesFormat === null) {
        _seriesFormat = function(d) { return d.key; };
      } else {
        _seriesFormat = seriesFormat;
      }

      return this;
    } else {
      return _seriesFormat;
    }
  };

  chart.xTickFormat(rsc.utils.multiTimeFormat);

  chart.render = function(update) {
    var x, y, chartData, h, w, m, svg, series, tiles, xAxis, yAxis, yStep, xBuffer,
      self = this;

    // force no color on series since the only chart color pretains to the heatmap
    this.color(function() {
      return 'black';
    });

    if (this.legend()) {
      this.modules.legend.key(this.seriesFormat());
      this.modules.legend.render(this.wrapper);
    } else {
      this.modules.legend.remove();
    }

    h = this.getChartHeight();
    w = this.getChartWidth();
    m = this.getChartMargin();

    x = d3.time.scale()
      .range([0, w]);

    y = d3.scale.ordinal()
      .rangePoints([h, 0]);

    z = d3.scale.linear()
      .range([THEME_MAPPINGS[this.theme()], 'steelblue']);

    xAxis = d3.svg.axis()
      .scale(x)
      .tickSize(0)
      .orient('bottom');

    xAxis.tickFormat(this.xTickFormat());

    yAxis = d3.svg.axis()
      .scale(y)
      .tickSize(0)
      .orient('left');

    // if (this.grid()) {
    //   xAxis.tickSize(-h);
    //   yAxis.tickSize(-w);
    // }

    chartData = this.data().filter(function(d) { return !d.disabled; });

    chartData = chartData.map(function(series, i) {
      series.values = series.values.map(function(d, idx) {
        if (idx === series.values.length - 2) {
          xBuffer = self.x()(series.values[idx + 1]) - self.x()(series.values[idx]);
        }

        d.internal_nextX = idx < series.values.length - 1 ? self.x()(series.values[idx + 1]) : null;
        d.internal_series = self.seriesFormat()(series);

        return d;
      });
      return series;
    });

    x.domain([
      d3.min(chartData, function(s) { return d3.min(s.values, self.x()); }),
      d3.max(chartData, function(s) { return d3.max(s.values, self.x()); })
    ]);
    x.domain([x.domain()[0], +x.domain()[1] + (xBuffer || 0)]);

    // Use empty value for filler space for the last real value
    y.domain(chartData.map(this.seriesFormat()).concat(['']));

    z.domain([0, d3.max(chartData, function(s) { return d3.max(s.values, self.y()); })]);

    function yAxisAdjust(g) {
      g.selectAll('g').each(function (d, i) {
        var node = d3.select(this);
        var textNode = node.select('text');
        var step = y(y.domain()[0]) - y(y.domain()[1]);

        textNode
          .attr('transform', 'translate(0,' + (-(step) / 2) + ')');
      });
    }

    svg = this.wrapper.select('.rsc-inner-wrapper');
    if (!svg.node()) {
      svg = this.wrapper.append('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom)
        .append('g')
          .attr('class', 'rsc-inner-wrapper')
          .attr('transform', 'translate(' + m.left + ',' + m.top + ')');
    } else {
      this.wrapper.select('svg')
        .attr('width', w + m.left + m.right)
        .attr('height', h + m.top + m.bottom);

      svg.attr('transform', 'translate(' + m.left + ',' + m.top + ')');
    }

    if (svg.select('.x.axis').node()) {
      if (this.transition()) {
        svg.select('.x.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(0,' + h + ')')
            .call(xAxis);
      } else {
        svg.select('.x.axis')
          .attr('transform', 'translate(0,' + h + ')')
          .call(xAxis);
      }
    } else {
      svg.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + h + ')')
        .call(xAxis);
    }

    if (svg.select('.y.axis').node()) {
      if (this.transition()) {
        svg.select('.y.axis')
          .transition().duration(this.duration())
            .attr('transform', 'translate(-1, 0)')
            .call(yAxis)
            .call(yAxisAdjust);
      } else {
        svg.select('.y.axis')
          .attr('transform', 'translate(-1, 0)')
          .call(yAxis)
          .call(yAxisAdjust);
      }
    } else {
      svg.append('g')
        .attr('class', 'y axis')
        .attr('transform', 'translate(-1, 0)')
        .call(yAxis)
        .call(yAxisAdjust);
    }

    yStep = y(y.domain()[0]) - y(y.domain()[1]);

    series = svg.selectAll('.series')
      .data(chartData, this.seriesFormat());

    series
      .enter().append('g')
        .attr('class', 'series');

    series.exit().remove();

    tiles = series.selectAll('.tile')
      .data(function(d) { return d.values; });

    tiles
      .enter().append('rect')
        .attr('class', 'tile')
        .attr('x', function(d) { return x(self.x()(d)); })
        .attr('y', function(d) { return y(d.internal_series) - yStep; })
        .attr('width', function(d) {
          if (!d.internal_nextX) {
            return x(x.invert(w)) - x(self.x()(d));
          } else {
            return x(d.internal_nextX) - x(self.x()(d));
          }
        })
        .attr('height', yStep)
        .style('opacity', 0);

    tiles.exit().remove();

    if (this.transition()) {
      tiles
        .transition().duration(this.duration())
          .attr('x', function(d) { return x(self.x()(d)); })
          .attr('y', function(d) { return y(d.internal_series) - yStep; })
          .attr('width', function(d) {
            if (!d.internal_nextX) {
              return x(x.invert(w)) - x(self.x()(d));
            } else {
              return x(d.internal_nextX) - x(self.x()(d));
            }
          })
          .attr('height', yStep)
          .style('fill', function(d) { return z(self.y()(d)); })
          .style('opacity', 1);
    } else {
      tiles
        .attr('x', function(d) { return x(self.x()(d)); })
        .attr('y', function(d) { return y(d.internal_series) - yStep; })
        .attr('width', function(d) {
          if (!d.internal_nextX) {
            return x(x.invert(w)) - x(self.x()(d));
          } else {
            return x(d.internal_nextX) - x(self.x()(d));
          }
        })
        .attr('height', yStep)
        .style('fill', function(d) { return z(self.y()(d)); })
        .style('opacity', 1);
    }

    tiles
      .on('click', function(d, i) {
        self.dispatch.click(d, i);
      })
      .on('dblclick', function(d, i) {
        self.dispatch.dblclick(d, i);
      })
      .on('mouseover', function(d, i) {
        rsc.interact.mouseover(
          series,
          this.parentNode,
          null,
          self.tooltips() ? {
            wrapper: self.wrapper,
            text: '<h3>' + (self.xFormat() ? self.xFormat()(self.x()(d)) : rsc.utils.timeFormat(self.x()(d))) + '</h3>' +
              '<p>' + (self.yFormat() ? self.yFormat()(self.y()(d)) : d3.format(',.0f')(self.y()(d))) + '</p>'
          } : null
        );

        self.dispatch.mouseover(d, i);
      })
      .on('mouseout', function(d, i) {
        rsc.interact.mouseout(series, self.tooltips() ? self.wrapper : null);

        self.dispatch.mouseout(d, i);
      })
      .on('mousemove', function(d, i) {
        if (self.tooltips()) {
          rsc.interact.mousemove(self.wrapper);
        }

        self.dispatch.mousemove(d, i);
      });

    if (this.legend()) {
      this.modules.legend.update();
    }

    return this;
  };

  return chart;
};
return rsc;})();
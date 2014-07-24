YUI.add('visualizer-datasource-cubes', function (Y) {
  Y.namespace('Visualizer.DataSource');

  function objectSize(obj) {
    var size = 0, key;
    for (key in obj) {
        if (obj.hasOwnProperty(key)) size++;
    }
    return size;
  }

  var DataSourceCubes = function() {
    this.DEFAULT_QUERY_TYPE = 'aggregate';
    this.MEMBERS_QUERY_TYPE = 'members';
    this.FACTS_QUERY_TYPE = 'facts';

    this.url = null;
    this.debug = false;
    this.connected = false;
    this.info = null;
    this.cubes = [];
    this.cubeCache = {};
    this.lastUrl = null;
    this.currentRequest = null;

    this.server = new cubes.Server(Y.bind(function(cfg) {
      this.currentRequest = Y.io(cfg.url, {
        context: this,
        data: cfg.data,
        xdr: { credentials: true },
        on: {
          complete: function() {
            if (cfg.complete) cfg.complete(cfg.url + (cfg.data ? '?' + Y.QueryString.stringify(cfg.data) : ''));
          },
          success: function(id, resp) {
            if (cfg.success) cfg.success(JSON.parse(resp.responseText));
          },
          failure: function(id, resp) {
            if (cfg.error) cfg.error(resp);
          }
        }
      });
    }, this));
  };

  DataSourceCubes.prototype = {
    _getCube: function(cubeName) {
      return this.cubeCache[cubeName];
    },

    _buildCubesList: function(cubeList) {
      this.cubes = [];

      for (var i = 0; i < cubeList.length; i++) {
        var cube = cubeList[i];

        this.cubes.push({
          key: cube.name,
          label: cube.label,
          category: cube.category
        });
      }

      this.cubes.sort(function(a, b) {
        if (a.label < b.label) return -1;
        if (a.label > b.label) return 1;
        return 0;
      });
    },

    _getDateCut: function(dateDim, config) {
      var dateCut = null;

      if (!Y.Lang.isUndefined(config.timeFrame) && !Y.Lang.isNull(config.timeFrame)) {
        var cutStart = null,
            cutEnd = null;

        if (!Y.Lang.isUndefined(config.timeFrame.start) && !Y.Lang.isNull(config.timeFrame.start)) {
          cutStart = Y.Date.parse(config.timeFrame.start.toString());
        }

        if (config.granularity === 'custom' && !Y.Lang.isUndefined(config.timeFrame.end) && !Y.Lang.isNull(config.timeFrame.end)) {
          cutEnd = Y.Date.parse(config.timeFrame.end.toString());
        }

        var from_path = null, to_path = null;

        var is_timegroup_level = function(lvl, timegroup) {
          if ( lvl.role === timegroup ) {
            return true;
          }
          if ( ( lvl.role === 'date' || lvl.name === 'date' ) && timegroup === 'day' ) {
            return true;
          }
          return false;
        };

        var converter = function(date, dim, drill_type, hier) {
          var path;

          if (hier) {
            path = [];

            for (var i = 0; i < hier.levels.length; i++) {
              var lvl = hier.levels[i];
              if (lvl.role === 'year') {
                path.push(date.getFullYear());
              } else if (lvl.role === 'quarter') {
                path.push(Math.floor(date.getMonth() / 3) + 1);
              } else if (lvl.role === 'month') {
                path.push(date.getMonth() + 1);
              } else if (lvl.name === 'week') {
                path.push(Y.Date.format(date, {format:'%Y-%m-%d'}));
              } else if (lvl.role === 'day') {
                path.push(date.getDate());
              } else if (lvl.role === 'hour') {
                path.push(date.getHours());
              } else if (lvl.role === 'minute') {
                path.push(date.getMinutes());
              // TODO remove the lvl.name legacy hacks below
              } else if (lvl.role === 'dow' || lvl.name === 'dow') {
                path.push(Y.Date.format(date, {format:'%A'}));
              } else if (lvl.role === 'date' || lvl.name === 'date') {
                path.push(Y.Date.format(date, {format:'%Y-%m-%d'}));
              }
              if ( is_timegroup_level(lvl, config.timeGroup) ) {
                break;
              }
            }
          } else {
            if (drill_type === 'dow') {
              path = [Y.Date.format(date, {format:'%A'})];
            } else if (drill_type === 'quarter') {
              path = [date.getFullYear(), Math.floor(date.getMonth() / 3) + 1, date.getMonth() + 1, date.getDate()];
            } else if (drill_type === 'week' || dim.name === 'minute_date_sf' || dim.name === 'day') {
              path = [Y.Date.format(date, {format:'%Y-%m-%d'})];

              if (drill_type === 'hour') {
                path.push(date.getHours());
              }
            } else if (drill_type === 'year') {
              path = [date.getFullYear()];
            } else if (drill_type === 'month') {
              path = [date.getFullYear(), (date.getMonth() + 1)];
            } else {
              path = [date.getFullYear(), (date.getMonth() + 1), date.getDate()];

              if (drill_type === 'hour') {
                path.push(date.getHours());
              } else if ( drill_type === 'minute') {
                path.push(date.getHours());
                path.push(date.getMinutes());
              }
            }
          }

          return path;
        };

        var cutHier = this.getDateHierarchy(dateDim, config.granularity === 'custom' ? 'day' : config.timeGroup);

        if (!Y.Lang.isUndefined(cutStart) && !Y.Lang.isNull(cutStart)) {
          from_path = converter(cutStart, dateDim, config.granularity === 'custom' ? 'day' : config.timeGroup, cutHier);
        }

        if (!Y.Lang.isUndefined(cutEnd) && !Y.Lang.isNull(cutEnd)) {
          to_path = converter(cutEnd, dateDim, config.granularity === 'custom' ? 'day' : config.timeGroup, cutHier);
        }

        if (from_path || to_path) {
          if (from_path && cutHier.levels.length < from_path.length) {
            from_path = from_path.slice(0, cutHier.levels.length);
          }
          if (to_path && cutHier.levels.length < to_path.length) {
            to_path = to_path.slice(0, cutHier.levels.length);
          }

          dateCut = new cubes.RangeCut(dateDim, cutHier, from_path, to_path, false).toString();
        }
      }

      return dateCut;
    },

    _getFilterCutString: function(cube, filters) {
      if (!cube) return;

      if (filters) {
        var cutStr;

        for (var i = 0; i < filters.length; i++) {
          var filter = filters[i];

          if (filter.disabled) continue;

          var filterDim;
          var filterVals = [];
          for (var k = 0; k < filter.info.length; k++) {
            var info = filter.info[k];
            filterVals.push(info.val);

            if (k === filter.info.length - 1) {
              filterDim = info.dim;
            }
          }

          if (filterVals.length > 0) {
            var drillObj = cubes.drilldown_from_string(cube, filterDim);
            var filterStr = new cubes.PointCut(drillObj.dimension, drillObj.hierarchy, filterVals, filter.invert).toString();

            if (filterStr) {
              var tmpStr = null;
              if (filterStr.indexOf('@') !== -1 && filterDim.indexOf('dow') !== -1) {
                tmpStr = 'dow';
              } else if (filterStr.indexOf('@') !== -1 && filterDim.indexOf('hour') !== -1) {
                tmpStr = 'hour';
              }

              if (tmpStr) {
                filterStr = filterStr.replace(filterStr.substring(filterStr.indexOf('@') + 1, filterStr.indexOf(':')), tmpStr);
              }

              if (cutStr) {
                cutStr += '|' + filterStr;
              } else {
                cutStr = filterStr;
              }
            }
          }
        }

        return cutStr;
      }
    },

    connect: function(successCb, failureCb) {
      this.server.connect(this.url, Y.bind(function(cubeList) {
        if (this.debug) {
          console.debug('SERVER:', this.server);
        }

        this.connected = true;
        this.info = this.server.info || {};
        this.info.url = this.server.url;
        this.url = this.server.url;

        this._buildCubesList(cubeList);

        if (successCb) successCb();
      }, this), Y.bind(function(resp) {
        this.connected = false;
        this.info = null;

        if (failureCb) failureCb(resp);
      }, this));
    },

    disconnect: function() {
      this.url = null;
      this.connected = false;
      this.info = null;
      this.cubes = [];
      this.cubeCache = {};
      this.lastUrl = null;
      this.currentRequest = null;
    },

    isConnected: function() {
      if (!this.server) {
        return false;
      } else if (this.server.url !== this.url) {
        return false;
      } else {
        return this.connected;
      }
    },

    isInProgress: function() {
      if (this.currentRequest && this.currentRequest.isInProgress()) {
        return true;
      } else {
        return false;
      }
    },

    abort: function() {
      if (this.isInProgress()) {
        this.currentRequest.abort();
        return true;
      } else {
        return false;
      }
    },

    loadCube: function(cubeName, successCb, failureCb) { // TODO: Failure Callback
      this.server.get_cube(cubeName, Y.bind(function(cube) {
        this.cubeCache[cube.name] = cube;

        if (successCb) {
          successCb(cube);
        }
      }, this));
    },

    load: function(config, successCb, failureCb) {
      if (!config) {
        if (failureCb) failureCb();
        return;
      }

      var data,
          queue = new Y.AsyncQueue();

      function loadLayer(layer, successCb, failureCb, isLastLayer) {
        queue.pause();

        var cube;
        if (layer.cube) {
          cube = this._getCube(layer.cube);
        }

        var args = {};

        if (layer.measure) {
          var agg = this.getMeasureAggregate(layer.cube, layer.measure);
          if (agg) {
            args.aggregates = agg.name;
          }
        }

        if (layer.drilldown && layer.drilldown !== this.getSplitDimensionString()) {
          args.drilldown = layer.drilldown;
        }

        if (layer.filters) {
          var filterCutString = this._getFilterCutString(cube, layer.filters) || '';

          if (layer.drilldown === this.getSplitDimensionString()) {
            args.split = filterCutString;
          } else {
            args.cut = filterCutString;
          }
        }

        var dateDim = layer.timeDimension ? this.getDimension(layer.cube, layer.timeDimension) : this.getDateDimension(layer.cube);

        var dateCut = this._getDateCut(dateDim, config);
        if (dateCut) {
          if (args.cut) {
            args.cut += '|' + dateCut;
          } else {
            args.cut = dateCut;
          }
        }

        var continueLoad = Y.bind(function() {
          var dateDrilldown;
          if (config.timeGroup) {
            var hier = this.getDateHierarchy(dateDim, config.timeGroup);

            // FIXME hacktacular
            dateDrilldown = dateDim.name + (hier ? hier.toString() : '') + ':' + config.timeGroup;
            if (new RegExp("^minute_date_sf.*:day$").test(dateDrilldown)) {
              dateDrilldown = dateDrilldown.replace(':day', ':date');
            }
          }

          if (dateDrilldown) {
            if (args.drilldown) {
              args.drilldown += '|' + dateDrilldown;
            } else {
              args.drilldown = dateDrilldown;
            }
          }

          if (this.debug) {
            console.debug('ALL ARGS:', layer.cube, args);
          }

          this.server.query(this.DEFAULT_QUERY_TYPE, cube, args, Y.bind(function(d) {
            d._cube = layer.cube;
            d._measure = layer.measure;
            d._drilldown = layer.drilldown;

            var cubeInfo = this.getCubeInfo(layer.cube, args.aggregates);
            if (cubeInfo && cubeInfo.measurement_type) {
              d._measurementType = cubeInfo.measurement_type;
            }

            if (!data) {
              data = [d];
            } else {
              data.push(d);
            }

            queue.run();

            if (isLastLayer && successCb) successCb(data);
          }, this), Y.bind(function(resp) {
            queue.run();
            if (isLastLayer && failureCb) failureCb(resp);
          }, this), Y.bind(function(resp) {
            if (resp) this.lastUrl = resp;
          }, this));
        }, this);

        if (layer.drilldown && layer.drilldown !== this.getSplitDimensionString() && (config.resultSize === 'top' || config.resultSize === 'bottom')) {
          if (!args.aggregates) {
            continueLoad();
          } else {
            var tbArgs = Y.merge({
              order: args.aggregates + ':' + (config.resultSize === 'bottom' ? 'asc' : 'desc'),
              page: 0,
              pagesize: 20
            }, args);

            if (this.debug) {
              console.debug('TOP/BOTTOM ARGS:', layer.cube, tbArgs);
            }

            this.server.query(this.DEFAULT_QUERY_TYPE, cube, tbArgs, Y.bind(function(d) {
              var tbFilterVals = [];

              var drilldownKey = layer.drilldown.replace(':', '.');
              var drillObj = cubes.drilldown_from_string(cube, layer.drilldown);
              var keys = drillObj.keysInResultCell();

              if (!d.cells || d.cells.length === 0) {
                if (!data) {
                  data = [];
                }

                queue.run();

                if (isLastLayer && successCb) successCb(data);

                return;
              }

              for (var i = 0; i < d.cells.length; i++) {
                var cell = d.cells[i];

                var tbFilterVal = [];
                for (var k = 0; k < keys.length; k++) {
                  var key = keys[k];
                  if (cell[key]) {
                    tbFilterVal.push(cell[key]);
                  }
                }

                tbFilterVals.push(tbFilterVal);
              }

              if (tbFilterVals.length > 0) {
                var filterStr = new cubes.SetCut(drillObj.dimension, drillObj.hierarchy, tbFilterVals).toString();

                if (filterStr) {
                  if (args.cut) {
                    args.cut += '|' + filterStr;
                  } else {
                    args.cut = filterStr;
                  }
                }
              }

              continueLoad();
            }, this), function(resp) {
              queue.run();

              if (isLastLayer && failureCb) failureCb(resp);
            });
          }
        } else {
          continueLoad();
        }
      }

      if (config.layers) {
        for (var i = 0; i < config.layers.length; i++) {
          var layer = config.layers[i];

          queue.add({
            fn: loadLayer,
            context: this,
            args: [layer, successCb, failureCb, i === config.layers.length - 1]
          });
        }

        queue.run();
      } else {
        if (failureCb) failureCb();
      }
    },

    isHighCardinality: function(cubeName, dimName, ignoreTopLevel, ignoreValues) {
      if (Y.Lang.isUndefined(ignoreTopLevel) || Y.Lang.isNull(ignoreTopLevel) || ignoreTopLevel === false) {
        var top = this.isTopLevel(cubeName, dimName, ignoreValues);
        if (top === false) return true;
      }

      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return false;

      var levelName = null;
      if (dimName.indexOf(':') !== -1) {
        var parts = dimName.split(':');
        dimName = parts[0];
        if ( dimName.indexOf('@') !== -1 ) {
          dimName = dimName.split('@')[0];
        }
        levelName = parts[1];
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return false;

      var level = ( levelName !== null ) ? dim.level(levelName) : null;

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return false;

      if (dim.cardinality === 'high' || (dim.info && dim.info.high_cardinality)) {
        return true;
      }

      if (Y.Lang.isUndefined(level) || Y.Lang.isNull(level)) return false;

      if (level.cardinality === 'high' || (level.info && level.info.high_cardinality)) {
        return true;
      }

      return false;
    },

    isCalculatedMeasure: function(cubeName, measure) {
      if (Y.Lang.isUndefined(measure) || Y.Lang.isNull(measure)) return false;

      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return false;

      var info = cube.aggregates;

      if (Y.Lang.isUndefined(info) || Y.Lang.isNull(info)) return false;

      for (var i = 0; i < info.length; i++) {
        if (info[i].ref === measure) {
          return info[i].is_calculated || false;
        }
      }

      return false;
    },

    isDateDimension: function(cubeName, dimName) {
      var dim = this.getDimension(cubeName, dimName);
      return this._isDateDimension(dim);
    },
    
    _isDateDimension: function(dim) {
      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return false;
      return (dim.role === "time" || dim.info && dim.info.is_date);
    },
    
    isValidTimeframe: function(cubeName, timeframe, dateDimName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return false;

      var dateDim;
      if (dateDimName) {
        dateDim = cube.dimension(dateDimName);
      } else {
        dateDim = this.getDateDimension(cubeName);
      }

      if (Y.Lang.isUndefined(dateDim) || Y.Lang.isNull(dateDim)) return false;

      for (var i = 0; i < dateDim.levels.length; i++) {
        var role = dateDim.levels[i].role;
        var name = dateDim.levels[i].name;
        if ( role === timeframe || name === timeframe || (timeframe === 'day' && name === 'date') ) {
          return true;
        }
      }

      return false;
    },

    getDateDimension: function(cubeName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return null;

      for (var i = 0; i < cube.dimensions.length; i++) {
        var dim = cube.dimensions[i];
        if (! this._isDateDimension(dim) ) continue;
        return dim;
      }
    },

    getDateDimensions: function(cubeName, timeframe) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return null;

      var dims = [];
      for (var i = 0; i < cube.dimensions.length; i++) {
        var dim = cube.dimensions[i];
        if ( ! this._isDateDimension(dim) ) continue;

        if (!Y.Lang.isUndefined(timeframe) && !Y.Lang.isNull(timeframe)) {
          var level = dim.level(timeframe);

          if (!level && timeframe === 'day') {
            level = dim.level('date');
          }

          if (Y.Lang.isUndefined(level) || Y.Lang.isNull(level)) continue;
        }

        dims.push(dim);
      }

      return dims;
    },

    getDateDimensionsInfo: function(cubeName, timeframe) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return null;

      var dims = [];
      for (var i = 0; i < cube.dimensions.length; i++) {
        var dim = cube.dimensions[i];
        if (! this._isDateDimension(dim) ) continue;

        if (!Y.Lang.isUndefined(timeframe) && !Y.Lang.isNull(timeframe)) {
          var level = dim.level(timeframe);

          if (!level && timeframe === 'day') {
            level = dim.level('date');
          }

          if (Y.Lang.isUndefined(level) || Y.Lang.isNull(level)) continue;
        }

        dims.push({
          val: dim.name,
          label: dim.label
        });
      }

      return dims;
    },

    getDateHierarchy: function(dim, type, mustBeSoleLevel) {
      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return null;

      if (Y.Lang.isUndefined(type) || Y.Lang.isNull(type)) return dim.hierarchy(dim.default_hierarchy_name);

      var i, hiers = [];
      for (var hier in dim.hierarchies) {
        for (i = 0; i < dim.hierarchies[hier].levels.length; i++) {
          var levelName = dim.hierarchies[hier].levels[i].name;
          if (levelName === type || (levelName === 'date' && type === 'day')) {
            if ( mustBeSoleLevel ) {
              if ( dim.hierarchies[hier].levels.length != 1 ) {
                continue;
              }
            }
            else if (dim.hierarchies[hier].name === dim.default_hierarchy_name) {
              return dim.hierarchy(dim.default_hierarchy_name);
            }

            if ( !mustBeSoleLevel || dim.hierarchies[hier].levels.length == 1 ) {
              hiers.push({
                name: dim.hierarchies[hier].name,
                index: i
              });
            }
          }
        }
      }

      var hierarchy;
      for (i = 0; i < hiers.length; i++) {
        if (i === 0) {
          hierarchy = hiers[i];
        } else if (hiers[i].index < hierarchy.index) {
          hierarchy = hiers[i];
        }
      }

      if (Y.Lang.isUndefined(hierarchy) || Y.Lang.isNull(hierarchy)) {
        return mustBeSoleLevel ? null : dim.hierarchy(dim.default_hierarchy_name);
      } else {
        return dim.hierarchy(hierarchy.name);
      }
    },

    getDefaultTimeFrame: function(cubeName) {
      var cube = this._getCube(cubeName);

      for (var i = 0; i < cube.dimensions.length; i++) {
        var dim = cube.dimensions[i];
        if ( this._isDateDimension(dim) ) {
          var hier = this.getDateHierarchy(dim);

          for (var k = 0; k < hier.levels.length; k++) {
            var level = hier.levels[k];
            if (level.name === 'day') {
              return level.name;
            }
          }

          return hier.levels[hier.levels.length - 1].name;
        }
      }

      return null;
    },

    getDateRange: function(cubeName) {
      var cube = this._getCube(cubeName);
      var max = new Date();
      var min;

      if (! Y.Lang.isUndefined(cube) && !Y.Lang.isNull(cube)) {
        if ( cube.info && cube.info.max_date ) {
          var newmax = new Date(cube.info.max_date + ' 00:00:00');
          if ( ! isNaN(newmax.getTime()) ) {
            max = newmax;
          }
        }
        if ( cube.info && cube.info.min_date ) {
          var newmin = new Date(cube.info.min_date + ' 00:00:00');
          if ( ! isNaN(newmin.getTime()) ) {
            min = newmin;
          }
        } else {
          min = new Date(max.getTime() - ( 5 * 365 * 24 * 60 * 60 * 1000 ));
        }
      } else {
        // 5 years before max
        min = new Date(max.getTime() - ( 5 * 365 * 24 * 60 * 60 * 1000 ));
      }

      return [ min, max ];
    },

    getMeasures: function(cubeName, dimName, ignoreTopLevel) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return [];

      var info = cube.aggregates;

      if (Y.Lang.isUndefined(info) || Y.Lang.isNull(info)) return [];

      var highCardinality = false;
      if (!Y.Lang.isUndefined(dimName) && !Y.Lang.isNull(dimName)) {
        highCardinality = this.isHighCardinality(cubeName, dimName, ignoreTopLevel);
      }

      var measures = [];

      for (var i = 0; i < info.length; i++) {
        if (highCardinality && info[i].is_calculated) continue;

        measures.push({
          key: info[i].ref,
          label: info[i].label || info[i].ref,
          measure: info.measure
        });
      }

      return measures;
    },

    getMeasureAggregate: function(cubeName, aggregateName) {
      var cube = this._getCube(cubeName);
      var aggregates = cube ? cube.aggregates : [];
      var agg = Y.Array.find(aggregates, function(m) { return m.ref === aggregateName; });
      return agg || ( aggregates.length > 0 ? aggregates[0] : null );
    },

    getMeasure: function(cubeName, measureName) {
      var cube = this._getCube(cubeName);
      var minfo = cube ? cube.aggregates : [];
      var meas = Y.Array.find(minfo, function(m) { return m.ref === measureName; });
      return meas || ( minfo.length > 0 ? minfo[0] : null );
    },

    getDimension: function(cubeName, dimName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube) || Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return null;

      var dim = cube.dimension(dimName);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return null;

      return dim;
    },

    getDimensions: function(cubeName, measure, ignoreValues, includeSplit) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return [];

      var calc = this.isCalculatedMeasure(cubeName, measure);

      var name;
      var drillMeasures = [];

      function insertDrillMeasure(key, label, topLevel) {
        var found = false;

        for (var n = 0; n < drillMeasures.length; n++) {
          if (drillMeasures[n].key === key)
          {
            found = true;
            break;
          }
        }

        if (!found) {
          drillMeasures.push({
            key: key,
            label: label,
            topLevel: topLevel
          });
        }
      }

      if (includeSplit) {
        insertDrillMeasure(this.getSplitDimensionString(), this.getSplitDimensionLabel(), true);
      }

      for (var i = 0; i < cube.dimensions.length; i++) {
        var dim = cube.dimensions[i];

        // if dimension is a time dimension, but not the default dimension, skip it.
        if ( this._isDateDimension(dim) && dim.name !== this.getDateDimension(cubeName).name) {
          continue;
        }

        // if dimension 
        if (dim.levels.length > 1) {
          var topLevel = null;
          for (var k = 0; k < dim.levels.length; k++) {
            if (calc && k > 0) break;

            var level = dim.levels[k];
            name = dim.name + ':' + level.name;

            if (!Y.Lang.isUndefined(ignoreValues) && !Y.Lang.isNull(ignoreValues) && ignoreValues.indexOf(name) !== -1) {
              continue;
            }

            if ( this._isDateDimension(dim) && level.name !== 'hour' && level.name !== 'dow') {
              continue;
            }

            if (level.name === 'hour' || level.name === 'dow' ) {
              // hierarchy must have only this level in it
              var hier = this.getDateHierarchy(dim, level.name, true);
              if (hier && hier.name) {
                name = name.replace(':', '@' + hier.name + ':');
              }
              else {
                continue;
              }

              topLevel = true;
            } else if (topLevel === null) {
              topLevel = true;
            } else {
              topLevel = false;
            }

            insertDrillMeasure(name, level.display_name(), topLevel);
          }
        } else {
          var subName = null;
          if (dim.levels.length === 1 && dim.levels[0]._label_attribute !== dim.name) {
            subName = ':' + dim.levels[0].name;
          } else {
            subName = '';
          }

          name = dim.name + subName;

          if (!Y.Lang.isUndefined(ignoreValues) && !Y.Lang.isNull(ignoreValues) && ignoreValues.indexOf(name) !== -1) {
            continue;
          }

          if (this._isDateDimension(dim) && dim.levels[0].name !== 'hour' && dim.levels[0].name !== 'dow') {
            continue;
          }

          insertDrillMeasure(name, dim.display_label(), true);
        }
      }

      return drillMeasures;
    },

    getDisplayName: function(cubeName, dimName) {
      var i,
          cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return;

      if (Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) {
        return cube.label;
      }

      if (dimName === this.getSplitDimensionString()) {
        return this.getSplitDimensionLabel();
      }

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return;

      for (i = 0; i < dim.levels.length; i++) {
        if (dim.levels[i].name === (typeof dimName === 'string' ? dimName : dimName[1])) {
          return dim.levels[i].display_name();
        }
      }

      if (typeof dimName !== 'string') {
        for (i = 0; i < dim.levels.length; i++) {
          if (dim.levels[i].name === dimName[0]) {
            for (var k = 0; k < dim.levels[i].attributes.length; k++) {
              if (dim.levels[i].attributes[k].name === dimName[1]) {
                return dim.levels[i].attributes[k].label;
              }
            }
          }
        }
      }
    },

    getMeasureDisplayName: function(cubeName, measure) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return;

      var info = cube.aggregates;

      if (Y.Lang.isUndefined(info) || Y.Lang.isNull(info)) return;

      if (Y.Lang.isUndefined(measure) || Y.Lang.isNull(measure)) {
        return info[0].label || info[i].ref;
      }

      for (var i = 0; i < info.length; i++) {
        if (info[i].ref === measure) {
          return info[i].label || info[i].ref;
        }
      }
    },

    getDisplayInfo: function(cubeName, dimName) {
      var i,
          cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return;

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return;

      for (i = 0; i < dim.levels.length; i++) {
        if (dim.levels[i].name === (typeof dimName === 'string' ? dimName : dimName[1])) {
          return {
            type: (this._isDateDimension(dim) ? 'date' : 'dim'),
            index: i,
            label: dim.levels[i].display_name()
          };
        }
      }

      if (typeof dimName !== 'string') {
        for (i = 0; i < dim.levels.length; i++) {
          if (dim.levels[i].name === dimName[0]) {
            for (var k = 0; k < dim.levels[i].attributes.length; k++) {
              if (dim.levels[i].attributes[k].name === dimName[1]) {
                return {
                  type: (this._isDateDimension(dim) ? 'date' : 'dim'),
                  index: k,
                  label: dim.levels[i].attributes[k].label
                };
              }
            }
          }
        }
      }
    },

    getMeasurementType: function(cubeName, measure) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return;

      var info = cube.aggregates;

      if (Y.Lang.isUndefined(info) || Y.Lang.isNull(info)) return;

      for (var i = 0; i < info.length; i++) {
        if (info[i].ref === measure) {
          return info[i].info ? info[i].info.measurement_type : null;
        }
      }
    },

    getMeasureDisplayInfo: function(cubeName, measure) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return;

      var info = cube.aggregates;

      if (Y.Lang.isUndefined(info) || Y.Lang.isNull(info)) return;

      for (var i = 0; i < info.length; i++) {
        if (info[i].ref === measure) {
          return {
            type: 'measure',
            index: i,
            label: info[i].label || info[i].ref
          };
        }
      }
    },

    getCubeInfo: function(cubeName, measureName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return null;
      var info = Y.merge(cube.info || {});

      if (!Y.Lang.isUndefined(measureName) && !Y.Lang.isNull(measureName)) {
        var meas = Y.Array.find(cube.aggregates, function(m) { return (m.ref === measureName); });
        info = Y.merge(info, ((meas && meas.info) || {}));
      }

      return info;
    },

    isTopLevel: function(cubeName, dimName, ignoreValues) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube) || Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return true;

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return true;

      var validIndex = -1;
      for (var i = 0; i < dim.levels.length; i++) {
        if (!Y.Lang.isUndefined(ignoreValues) && !Y.Lang.isNull(ignoreValues)) {
          var found = false;
          for (var k = 0; k < ignoreValues.length; k++) {
            var tmpVal = ignoreValues[k].split(':');
            if (typeof tmpVal === 'string') {
              if (dim.levels[i].name === tmpVal) {
                found = true;
                break;
              }
            } else {
              if (dim.levels[i].name === tmpVal[1]) {
                found = true;
                break;
              }
            }
          }

          if (!found) {
            validIndex += 1;
          }
        } else {
          validIndex = i;
        }

        if (dim.levels[i].name === (typeof dimName === 'string' ? dimName : dimName[1])) {
          return validIndex === 0;
        }
      }

      return true;
    },

    findLevel: function(cubeName, dimName) {
      var cube = this._getCube(cubeName);
      var d, level;

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube) || Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return null;

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
        d = dimName[0];
        level = dimName[1];
      } else {
        d = dimName;
        level = null;
      }

      if (Y.Lang.isUndefined(level) || Y.Lang.isNull(level)) return null;

      var dim = cube.dimension(d);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return null;

      if (dim.levels) {
        for (var i = 0; i < dim.levels.length; i++) {
          if (dim.levels[i].name === level) {
            return dim.levels[i];
          }
        }
      }

      return null;
    },

    getLevels: function(cubeName, dimName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube) || Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return null;

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return null;

      return dim.levels;
    },

    getNextLevel: function(cubeName, dimName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube) || Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return null;

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return null;

      var isNext = false;
      var nextLevel;
      for (var i = 0; i < dim.levels.length; i++) {
        if (dim.levels[i].name === (typeof dimName === 'string' ? dimName : dimName[1])) {
          isNext = true;
        } else if (isNext) {
          nextLevel = dim.levels[i];
          break;
        }
      }

      if (Y.Lang.isUndefined(nextLevel) || Y.Lang.isNull(nextLevel)) return null;

      return dimName[0] + ':' + nextLevel.name;
    },

    getOrderAttribute: function(cubeName, dimName) {
      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube) || Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return null;

      if (dimName.indexOf('@') !== -1) {
        dimName = dimName.replace(dimName.substring(dimName.indexOf('@'), dimName.indexOf(':')), '');
      }

      if (dimName.indexOf(':') !== -1) {
        dimName = dimName.split(':');
      }

      var dim = cube.dimension(typeof dimName === 'string' ? dimName : dimName[0]);

      if (Y.Lang.isUndefined(dim) || Y.Lang.isNull(dim)) return null;

      for (var i = 0; i < dim.levels.length; i++) {
        if (dim.levels[i].name === (typeof dimName === 'string' ? dimName : dimName[1])) {
          return dim.name + ':' + dim.levels[i]._order_attribute;
        }
      }

      return null;
    },

    getDrillInfo: function(cubeName, dimName) {
      if (Y.Lang.isUndefined(dimName) || Y.Lang.isNull(dimName)) return null;

      var cube = this._getCube(cubeName);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return null;

      var dd = cubes.drilldown_from_string(cube, dimName);

      if (Y.Lang.isUndefined(dd) || Y.Lang.isNull(dd)) return null;

      return {
        keys: dd.keysInResultCell(),
        labels: dd.labelsInResultCell()
      };
    },

    getSplitDimensionString: function() {
      return cubes.SPLIT_DIMENSION_STRING;
    },

    getSplitDimensionLabel: function(matches) {
      if (Y.Lang.isUndefined(matches) || Y.Lang.isNull(matches) || matches === true) {
        return 'Matches Filters';
      } else {
        return 'Does Not Match Filters';
      }
    },

    getNullString: function() {
      return cubes.NULL_PART_STRING;
    },

    getFields: function(cubeName) {
      var cube = this._getCube(cubeName);

      var i, k, n,
          fields = [];

      function addField(key, label, type, parent) {
        fields.push({
          key: key,
          label: label ? label : key,
          type: type,
          parent: parent
        });
      }

      if (!Y.Lang.isUndefined(cube) && !Y.Lang.isNull(cube)) {
        if (cube.measures) {
          for (i = 0; i < cube.measures.length; i++) {
            var measure = cube.measures[i];

            addField(measure.ref, measure.label, 'measure');
          }
        }

        if (cube.details) {
          for (i = 0; i < cube.details.length; i++) {
            var detail = cube.details[i];

            addField(detail.name, detail.label, 'detail');
          }
        }

        if (cube.dimensions) {
          for (i = 0; i < cube.dimensions.length; i++) {
            var dim = cube.dimensions[i];

            if (dim.levels) {
              for (k = 0; k < dim.levels.length; k++) {
                var level = dim.levels[k];

                if (level.attributes) {
                  for (n = 0; n < level.attributes.length; n++) {
                    var attr = level.attributes[n];
                    var label = attr.label;

                    if (Y.Lang.isUndefined(label) || Y.Lang.isNull(label) || label === '') {
                      if (level.attributes.length > 1) {
                        label = level.display_name() + ': ' + attr.name;
                      } else {
                        label = level.display_name();
                      }
                    }

                    addField(attr.ref, label, (this._isDateDimension(dim) ? 'date' : 'attribute'), level.dimension_name + ':' + level.name);
                  }
                } else {
                  addField(level.name, level.display_name(), (this._isDateDimension(dim) ? 'date' : 'level'));
                }
              }
            } else {
              addField(dim.name, dim.display_label(), (this._isDateDimension(dim) ? 'date' : 'dimension'));
            }
          }
        }
      }

      return fields;
    },

    queryMembers: function(cubeName, dimName, filters, successCb, failureCb) {
      var cube = this._getCube(cubeName);
      var drillInfo = this.getDrillLevelInfo(cubeName, dimName);

      if (Y.Lang.isUndefined(drillInfo) || Y.Lang.isNull(drillInfo)) {
        if (failureCb) failureCb();
        return;
      }

      var args = {
        depth: drillInfo.levels.length
      };

      var dim = drillInfo.levels[drillInfo.levels.length - 1].dim;

      if (drillInfo.levels[drillInfo.levels.length - 1].hier) {
        args.hierarchy = drillInfo.levels[drillInfo.levels.length - 1].hier;
      }

      if (filters) {
        var filterCutString = this._getFilterCutString(cube, filters) || '';

        args.cut = filterCutString;
      }

      if (this.debug) {
        console.debug('QUERY MEMBERS:', args);
      }

      this.server.query(this.MEMBERS_QUERY_TYPE + '/' + dim, cube, args, Y.bind(function(data) {
        if (successCb) successCb(data);
      }, this), Y.bind(function(resp) {
        if (failureCb) failureCb(resp);
      }, this));
    },

    exportFacts: function(config, layer, fields, format) {
      var node = Y.one('#cubes-export-hidden');
      if (!node) {
        node = Y.Node.create('<div>').set('id', 'cubes-export-hidden').setStyle('display', 'none');
        Y.one('body').append(node);
      } else {
        node.empty();
      }

      var cube = this._getCube(layer.cube);

      if (Y.Lang.isUndefined(cube) || Y.Lang.isNull(cube)) return null;

      var args = {};

      if (fields) {
        args.fields = fields.join(',');
      }

      if (format) {
        args.format = format;
      } else {
        args.format = 'csv';
      }

      if (args.format === 'csv') {
        args.header = 'labels';
      }

      if (layer.filters) {
        var filterCutString = this._getFilterCutString(cube, layer.filters) || '';

        if (layer.drilldown === this.getSplitDimensionString()) {
          args.split = filterCutString;
        } else {
          args.cut = filterCutString;
        }
      }

      var dateDim = layer.timeDimension ? this.getDimension(layer.cube, layer.timeDimension) : this.getDateDimension(layer.cube);

      var dateCut = this._getDateCut(dateDim, config);
      if (dateCut) {
        if (args.cut) {
          args.cut += '|' + dateCut;
        } else {
          args.cut = dateCut;
        }
      }

      if (args.cut) args.cut = args.cut.toString();

      var url = this.server.url + 'cube/' + cube.name + '/' + this.FACTS_QUERY_TYPE;

      var qs = Y.QueryString.stringify(args);

      var frame = new Y.Frame({
        container: node,
        src: url + '?' + qs
      }).render();
    },

    exportData: function(config, layer, format) {
      var node = Y.one('#cubes-export-hidden');
      if (!node) {
        node = Y.Node.create('<div>').set('id', 'cubes-export-hidden').setStyle('display', 'none');
        Y.one('body').append(node);
      } else {
        node.empty();
      }

      var args = {};

      if (format) {
        args.format = format;
      } else {
        args.format = 'csv';
      }

      var frame = new Y.Frame({
        container: node,
        src: this.lastUrl + '&format=' + (format || 'csv')
      }).render();
    },

    getDrillLevelInfo: function(cubeName, dimName) {
      var nextLevel, levels, i, dim, levelName, fullName,
          isLastLevel = false,
          prevLevels = [];

      var drill = cubes.drilldown_from_string(this._getCube(cubeName), dimName);
      dim = drill.dimension;
      hier = drill.hierarchy || drill.dimension.hierarchy();
      levels = drill.hierarchy.levels;
      levelName = drill.level.name;

      for (i = 0; i < levels.length; i++) {
        prevLevels.push({
          dim: dim.name,
          hier: (hier ? hier.name : null),
          name: dim.name + ':' + levels[i].name,
          key: levels[i].key().ref.replace(':', '.'),
          labelKey: levels[i].label_attribute().ref.replace(':', '.')
        });

        if (levels[i].name === levelName) {
          if (i < levels.length - 1) {
            nextLevel = dim + ':' + levels[i + 1].name;
          }
          else {
            isLastLevel = true;
          }
          break;
        }
      }

      return {
        levels: prevLevels,
        nextLevel: nextLevel,
        isLastLevel: isLastLevel
      };
    },

    isFullyNonadditive: function(cubeName, measureName, dimName) {
      var measure = this.getMeasure(cubeName, measureName);

      if (measure && measure.nonadditive === 'all') {
        return true;
      }

      var levels = this.getLevels(cubeName, dimName);

      if (levels) {
        for (var i = 0; i < levels.length; i++) {
          if (levels[i].nonadditive === 'all') {
            return true;
          }
        }
      }

      return false;
    },

    get: function(prop) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      return this[prop];
    },

    set: function(prop, val) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      this[prop] = val;

      return this[prop];
    }
  };

  Y.Visualizer.DataSource.Cubes = DataSourceCubes;
}, '1.0', {
  requires: ['io', 'node', 'datatype-date', 'frame', 'async-queue']
});

YUI.add('visualizer-datalayer', function (Y) {
  Y.namespace('Visualizer');

  function objectSize(obj) {
    var size = 0, key;
    for (key in obj) {
        if (obj.hasOwnProperty(key)) size++;
    }
    return size;
  }

  var DataLayer = function() {
    this.MAX_UNIQUE = 25;

    this.debug = false;
    this.raw = null;
    this.DataSource = null;
    this.data = null;
    this.type = null;
    this.display = null;
    this.yMax = null;
  };

  DataLayer.prototype = {
    load: function(data, DataSource) {
      this.raw = data;
      this.DataSource = DataSource;
      this.data = null;
      this.type = null;
      this.display = null;
      this.yMax = null;

      if (this.debug) {
        console.debug('RAW DATA:', this.raw);
      }

      return this;
    },

    parse: function(config) {
      this.data = null;
      this.type = null;
      this.display = null;
      this.yMax = null;

      this.debug = this.DataSource.get('debug');

      function sortByString(key) {
        return function(a, b) {
          if (a[key] < b[key]) return -1;
          if (a[key] > b[key]) return 1;
          return 0;
        };
      }

      function parseISODate(isodate) {
        var parts = isodate.split('-');
        if ( parts.length != 3 ) {
          return null;
        }
        return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10)-1, parseInt(parts[2], 10));
      }

      function parseDate(level, cell) {
        var dateObj = new Date(new Date().getFullYear(), 0, 1);
        if (!Y.Lang.isUndefined(cell[level + '.date']) && !Y.Lang.isNull(cell[level + '.date'])) {
          dateObj = parseISODate(cell[level + '.date']);
        } else if (level === 'week' && !Y.Lang.isUndefined(cell[level]) && !Y.Lang.isNull(cell[level])) {
          dateObj = parseISODate(cell[level]);
        } else if (!Y.Lang.isUndefined(cell[level + '.week']) && !Y.Lang.isNull(cell[level + '.week'])) {
          dateObj = parseISODate(cell[level + '.week']);
        } else {
          var qtr;
          dateObj = new Date(new Date().getFullYear(), 0, 1);
          if (level === 'year' && !Y.Lang.isUndefined(cell[level]) && !Y.Lang.isNull(cell[level])) {
            dateObj.setFullYear(cell[level]);
          } else if (!Y.Lang.isUndefined(cell[level + '.year']) && !Y.Lang.isNull(cell[level + '.year'])) {
            dateObj.setFullYear(cell[level + '.year']);
          }
          if (level === 'quarter' && !Y.Lang.isUndefined(cell[level]) && !Y.Lang.isNull(cell[level])) {
            qtr = cell[level];
            if ( qtr >= 1 && qtr <= 4 ) {
              dateObj.setMonth( ( qtr - 1 ) * 3 );
            }
          } else if (!Y.Lang.isUndefined(cell[level + '.quarter']) && !Y.Lang.isNull(cell[level + '.quarter'])) {
            qtr = cell[level + '.quarter'];
            if ( qtr >= 1 && qtr <= 4 ) {
              dateObj.setMonth( ( qtr - 1 ) * 3 );
            }
          }
          if (level === 'month' && !Y.Lang.isUndefined(cell[level]) && !Y.Lang.isNull(cell[level])) {
            dateObj.setMonth(cell[level] - 1);
          } else if (!Y.Lang.isUndefined(cell[level + '.month']) && !Y.Lang.isNull(cell[level + '.month'])) {
            dateObj.setMonth(cell[level + '.month'] - 1);
          }
          if (level === 'day' && !Y.Lang.isUndefined(cell[level]) && !Y.Lang.isNull(cell[level])) {
            dateObj.setDate(cell[level]);
          } else if (!Y.Lang.isUndefined(cell[level + '.day']) && !Y.Lang.isNull(cell[level + '.day'])) {
            dateObj.setDate(cell[level + '.day']);
          } else {
            dateObj.setDate(1);
          }
        }

        if (config.timeGroup === 'hour' || config.timeGroup === 'minute') {
          var min;
          if (level === 'hour' && !Y.Lang.isUndefined(cell[level]) && !Y.Lang.isNull(cell[level])) {
            dateObj.setHours(cell[level]);
            min = cell[level];
          } else if (!Y.Lang.isUndefined(cell[level + '.hour']) && !Y.Lang.isNull(cell[level + '.hour'])) {
            dateObj.setHours(cell[level + '.hour']);
            min = cell[level + '.minute'];
          }

          if (!Y.Lang.isUndefined(min) && !Y.Lang.isNull(min)) {
            dateObj.setMinute(min);
          }
        }

        // TODO second, 5-30minute, 15second, 30second, isocalendar?

        var dt = Y.Date.format(dateObj, { format: '%Y-%m-%d %H:%M:%S' });

        return dt;
      }

      function normalizeKey(key) {
        if (Y.Lang.isUndefined(key) || Y.Lang.isNull(key)) {
          return '(null)';
        } else {
          return key;
        }
      }

      var getMeasureField = Y.bind(function(cube, measure) {
        var meas = this.DataSource.getMeasure(cube, measure);
        return meas ? meas.ref : null;
      }, this);

      var getKeyField = Y.bind(function(cube, drilldown) {
        var keyField;
        var drillInfo = this.DataSource.getDrillInfo(cube, drilldown);

        if (!Y.Lang.isUndefined(drillInfo) && !Y.Lang.isNull(drillInfo)) {
          if (!Y.Lang.isUndefined(drillInfo.labels) && !Y.Lang.isNull(drillInfo.labels)) {
            keyField = drillInfo.labels[drillInfo.labels.length - 1] || drilldown;
          } else if (!Y.Lang.isUndefined(drillInfo.keys) && !Y.Lang.isNull(drillInfo.keys)) {
            keyField = drillInfo.keys[drillInfo.keys.length - 1] || drilldown;
          }
        } else {
          keyField = drilldown;
        }

        if (!Y.Lang.isUndefined(keyField) && !Y.Lang.isNull(keyField)) {
          if (keyField.indexOf('@') !== -1) {
            keyField = keyField.replace(keyField.substring(keyField.indexOf('@'), keyField.indexOf(':') + 1), '.');
          } else {
            keyField = keyField.replace(':', '.');
          }
        }

        return keyField;
      }, this);

      var getLevelKeyFields = Y.bind(function(cube, drilldown) {
        var keyFields;
        var drillInfo = this.DataSource.getDrillInfo(cube, drilldown);

        if (!Y.Lang.isUndefined(drillInfo) && !Y.Lang.isNull(drillInfo)) {
          if (!Y.Lang.isUndefined(drillInfo.labels) && !Y.Lang.isNull(drillInfo.labels)) {
            keyFields = drillInfo.labels.slice(0, drillInfo.labels.length - 1) || [drilldown];
          } else if (!Y.Lang.isUndefined(drillInfo.keys) && !Y.Lang.isNull(drillInfo.keys)) {
            keyFields = drillInfo.keys.slice(0, drillInfo.keys.length - 1) || [drilldown];
          }
        } else {
          keyFields = [drilldown];
        }

        if (!Y.Lang.isUndefined(keyFields) && !Y.Lang.isNull(keyFields)) {
          for (var i = 0; i < keyFields.length; i++) {
            if (!Y.Lang.isUndefined(keyFields[i]) && !Y.Lang.isNull(keyFields[i])) {
              if (keyFields[i].indexOf('@') !== -1) {
                keyFields[i] = keyFields[i].replace(keyFields[i].substring(keyFields[i].indexOf('@'), keyFields[i].indexOf(':') + 1), '.');
              } else {
                keyFields[i] = keyFields[i].replace(':', '.');
              }
            }
          }
        }

        return keyFields;
      }, this);

      var getOrderField = Y.bind(function(cube, drilldown) {
        var orderField = this.DataSource.getOrderAttribute(cube, drilldown);
        if (!Y.Lang.isUndefined(orderField) && !Y.Lang.isNull(orderField) && orderField.indexOf(':') !== -1) {
          orderField = orderField.replace(':', '.');
        }

        return orderField;
      }, this);

      var parseDefault = Y.bind(function() {
        var count = 0;

        for (var i = 0; i < this.raw.length; i++) {
          var d = this.raw[i];

          var measureField = getMeasureField(d._cube, d._measure);

          if (d.cells.length === 0) {
            count += d.summary[measureField];
          } else {
            for (var k = 0; k < d.cells.length; k++) {
              count += d.cells[k][measureField];
            }
          }
        }

        return {
          data: {
            count: count
          },
          display: null
        };
      }, this);

      var parseSlices = Y.bind(function(defaultDisplay) {
        var data = [];

        for (var i = 0; i < this.raw.length; i++) {
          var d = this.raw[i];

          var keyField = getKeyField(d._cube, d._drilldown);
          var levelKeyFields = getLevelKeyFields(d._cube, d._drilldown);
          var measureField = getMeasureField(d._cube, d._measure);
          var orderField = getOrderField(d._cube, d._drilldown);

          for (var k = 0; k < d.cells.length; k++) {
            var cell = d.cells[k];

            var key = null;
            if (keyField) {
              if (levelKeyFields && (levelKeyFields.length > 1 || levelKeyFields[0] !== keyField)) {
                for (var m = 0; m < levelKeyFields.length; m++) {
                  if (Y.Lang.isNull(key) || Y.Lang.isUndefined(key)) {
                    key = normalizeKey(cell[levelKeyFields[m]]);
                  } else {
                    key += ' : ' + normalizeKey(cell[levelKeyFields[m]]);
                  }
                }
              }

              if (Y.Lang.isNull(key) || Y.Lang.isUndefined(key)) {
                key = normalizeKey(cell[keyField]);
              } else {
                key += ' : ' + normalizeKey(cell[keyField]);
              }
            } else {
              key = normalizeKey(this.DataSource.getMeasureDisplayName(d._cube, d._measure));
            }

            if (keyField === this.DataSource.getSplitDimensionString()) {
              key = this.DataSource.getSplitDimensionLabel(key);
            }
            if (keyField && this.raw.length > 1) {
              key = this.DataSource.getMeasureDisplayName(d._cube, d._measure) + ' - ' + key;
            }

            var order = orderField ? cell[orderField] : key;
            var count = cell[measureField];

            // prevent duplicates
            var found = false;
            for (var n = 0; n < data.length; n++) {
              if (data[n].key === key) {
                data[n].count += count;
                found = true;
                break;
              }
            }

            if (!found) {
              data.push({
                key: key,
                order: order,
                count: count,
                raw: cell
              });
            }
          }
        }

        // take top MAX_UNIQUE values
        if (data.length > this.MAX_UNIQUE) {
          data.sort(function(a, b) {
            return b.count - a.count;
          });

          data = data.slice(0, this.MAX_UNIQUE);
        }

        data.sort(sortByString('key'));

        if (data.length === 1) {
          return parseDefault();
        }

        return {
          data: data,
          display: defaultDisplay ? 'bar' : config.display
        };
      }, this);

      var parsePaths = Y.bind(function(defaultDisplay) {
        var i, k, n, p, dt, found,
            data = [];

        for (i = 0; i < this.raw.length; i++) {
          var d = this.raw[i];

          var keyField = getKeyField(d._cube, d._drilldown);
          var levelKeyFields = getLevelKeyFields(d._cube, d._drilldown);
          var measureField = getMeasureField(d._cube, d._measure);
          var orderField = getOrderField(d._cube, d._drilldown);

          var level;
          for (var dim_hier_key in d.levels) {
            var pp = dim_hier_key.split('@');
            var dim = pp[0];
            var hier = ( pp.length > 0 ) ? pp[1] : null;
            if (this.DataSource.isDateDimension(d._cube, dim) && (dim + '.' + d.levels[dim_hier_key][0] !== keyField)) {
              level = dim;
              break;
            }
          }

          for (k = 0; k < d.cells.length; k++) {
            var cell = d.cells[k];

            var key = null;
            if (keyField) {
              if (levelKeyFields && (levelKeyFields.length > 1 || levelKeyFields[0] !== keyField)) {
                for (var m = 0; m < levelKeyFields.length; m++) {
                  if (Y.Lang.isNull(key) || Y.Lang.isUndefined(key)) {
                    key = normalizeKey(cell[levelKeyFields[m]]);
                  } else {
                    key += ' : ' + normalizeKey(cell[levelKeyFields[m]]);
                  }
                }
              }

              if (Y.Lang.isNull(key) || Y.Lang.isUndefined(key)) {
                key = normalizeKey(cell[keyField]);
              } else {
                key += ' : ' + normalizeKey(cell[keyField]);
              }
            } else {
              key = normalizeKey(this.DataSource.getMeasureDisplayName(d._cube, d._measure));
            }

            if (keyField === this.DataSource.getSplitDimensionString()) {
              key = this.DataSource.getSplitDimensionLabel(key);
            }
            if (keyField && this.raw.length > 1) {
              key = this.DataSource.getMeasureDisplayName(d._cube, d._measure) + ' - ' + key;
            }

            var order = orderField ? cell[orderField] : key;
            var count = cell[measureField];

            dt = parseDate(level, cell);

            found = false;
            for (n = 0; n < data.length; n++) {
              if (data[n].key === key) {
                var valFound = false;
                for (p = 0; p < data[n].values.length; p++) {
                  var val = data[n].values[p];
                  if (val.dt === dt) {
                    valFound = true;
                    val.count += count;
                    if (Y.Lang.isNull(this.yMax) || val.count > this.yMax) {
                      this.yMax = val.count;
                    }
                    break;
                  }
                }

                if (!valFound) {
                  data[n].values.push({
                    key: key,
                    dt: dt,
                    count: count,
                    raw: cell
                  });

                  if (Y.Lang.isNull(this.yMax) || count > this.yMax) {
                    this.yMax = count;
                  }
                }

                data[n].sum += count;

                found = true;
                break;
              }
            }

            if (!found) {
              data.push({
                key: key,
                order: order,
                values: [{
                  key: key,
                  dt: dt,
                  count: count,
                  raw: cell
                }],
                sum: count,
                raw: cell
              });
            }
          }
        }

        // take top MAX_UNIQUE values
        if (data.length > this.MAX_UNIQUE) {
          data.sort(function(a, b) {
            return b.sum - a.sum;
          });

          data = data.slice(0, this.MAX_UNIQUE);
        }

        // get all possible dates
        var allDates = {};
        for (i = 0; i < data.length; i++) {
          for (k = 0; k < data[i].values.length; k++) {
            dt = data[i].values[k].dt;
            if (!allDates[dt]) allDates[dt] = true;
          }
        }

        if (Y.Object.size(allDates) === 1) {
          return parseSlices(true);
        }

        // assure each series has all possible date values and then sort the values
        for (i = 0; i < data.length; i++) {
          for (dt in allDates) {
            found = false;
            for (k = 0; k < data[i].values.length; k++) {
              if (data[i].values[k].dt === dt) {
                found = true;
                break;
              }
            }

            if (!found) {
              data[i].values.push({
                key: data[i].key,
                dt: dt,
                count: 0
              });
            }
          }

          data[i].values.sort(sortByString('dt'));
        }

        return {
          data: data,
          display: defaultDisplay ? 'line' : config.display
        };
      }, this);

      var parseTable = Y.bind(function(cells) {
        var i, k, n, key, d, di,
            sharedKeys = {},
            uniqueKeys = {},
            layersData = [],
            data = [];

        for (i = 0; i < this.raw.length; i++) {
          d = this.raw[i];

          var keyField = getKeyField(d._cube, d._drilldown);

          var layerData = [];
          for (k = 0; k < d.cells.length; k++) {
            var cell = d.cells[k];

            var newObj = {};
            for (key in cell) {
              var newKey;
              if (key === d._measure) {
                newKey = this.DataSource.getMeasureDisplayName(d._cube, d._measure);
              } /*else if (keyField && key === keyField) {
                if (keyField === this.DataSource.getSplitDimensionString()) {
                  newKey = this.DataSource.getSplitDimensionLabel(key);
                }
                if (keyField && this.raw.length > 1) {
                  newKey = this.DataSource.getMeasureDisplayName(d._cube, d._measure) + ' - ' + key.replace('.', ':');
                }
              }*/ else {
                newKey = key.replace('.', ':');
                sharedKeys[newKey] = true;
              }

              newObj[newKey] = cell[key];

              uniqueKeys[newKey] = true;
            }

            layerData.push(newObj);
          }

          layersData.push(layerData);
        }

        for (i = 0; i < layersData.length; i++) {
          di = layersData[i];

          for (k = 0; k < di.length; k++) {
            d = di[k];

            var hasSharedKeys = true;
            for (key in sharedKeys) {
              if (!Y.Object.owns(d, key)) {
                hasSharedKeys = false;
                break;
              }
            }

            if (!hasSharedKeys) {
              data.push(d);
            } else {
              var found = false;
              for (n = 0; n < data.length; n++) {
                var mergeData = true;
                for (key in sharedKeys) {
                  if (Y.Object.owns(d, key) && d[key] !== data[n][key]) {
                    mergeData = false;
                    break;
                  }
                }

                if (mergeData) {
                  found = true;
                  data[n] = Y.merge(data[n], d);
                  break;
                }
              }

              if (!found) {
                data.push(d);
              }
            }
          }
        }

        for (i = 0; i < data.length; i++) {
          for (key in uniqueKeys) {
            if (!Y.Object.owns(data[i], key)) {
              data[i][key] = null;
            }
          }
        }

        return {
          data: data,
          display: config.display
        };
      }, this);

      var type = null;
      for (var i = 0; i < this.raw.length; i++) {
        var d = this.raw[i];

        if (d._measurementType) {
          type = d._measurementType;
        }
      }
      this.type = type;

      var parsed;
      if (Y.Lang.isUndefined(config.display) || Y.Lang.isNull(config.display) || config.display === 'text') {
        parsed = parseDefault(this.raw.cells, this.raw.summary);
      } else if (config.display === 'bar' || config.display === 'pie' || config.display === 'donut') {
        parsed = parseSlices(this.raw.cells);
      } else if (config.display === 'line' || config.display === 'index' ||
        config.display === 'stacked' || config.display === 'expanded' || config.display === 'stream' || config.display === 'heatmap')
      {
        parsed = parsePaths(this.raw.levels, this.raw.cells);
      } else if (config.display === 'table' || config.display === 'top' || config.display === 'bottom') {
        parsed = parseTable(this.raw.cells);
      }

      this.data = parsed ? parsed.data : [];
      this.display = parsed ? parsed.display : config.display;

      // sort data
      if (Object.prototype.toString.call(this.data) === '[object Array]' &&
        this.display !== 'table' && this.display !== 'top' && this.display !== 'bottom')
      {
        this.data.sort(sortByString('order'));
      }

      if (this.debug) {
        console.debug('DISPLAY DATA:', this.data);
      }

      return this;
    },

    set: function(prop, val) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      if (prop === 'data' || prop === 'raw') return;

      this[prop] = val;

      return this[prop];
    },

    get: function(prop) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      return this[prop];
    }
  };

  Y.Visualizer.DataLayer = DataLayer;
}, '1.0', {
  requires: ['datatype-date-format']
});

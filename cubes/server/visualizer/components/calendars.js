YUI.add('visualizer-component-calendars', function (Y) {
  Y.namespace('Visualizer.Component');

  var NAV_LABEL = null;
  var START_SELECTED_DATE = null;
  var END_SELECTED_DATE = null;
  var MONTH_NAMES = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december'
  ];

  var Calendars = function(config) {
    this.el = config.el;
    this.node = Y.one(config.el);
    this.hidden = config.hidden;

    var minDate = new Date();
    minDate.setFullYear(minDate.getFullYear() - 50);

    this.start = new Y.Calendar({
      id: 'start',
      contentBox: this.el + ' .start',
      width: 200,
      showPrevMonth: true,
      showNextMonth: true,
      date: new Date(),
      minimumDate: this._convertMinDate(minDate),
      maximumDate: this._convertMaxDate(new Date())
    }).render();

    this.end = new Y.Calendar({
      id: 'end',
      contentBox: this.el + ' .end',
      width: 200,
      showPrevMonth: true,
      showNextMonth: true,
      date: new Date(),
      minimumDate: this._convertMinDate(minDate),
      maximumDate: this._convertMaxDate(new Date())
    }).render();

    this.timeGroup = null;
  };

  Calendars.prototype = {
    _convertMinDate: function(dt) {
      dt = new Date(dt);
      dt.setHours(0);
      dt.setMinutes(0);
      dt.setSeconds(0);
      dt.setMilliseconds(0);
      return dt;
    },

    _convertMaxDate: function(dt) {
      dt = new Date(dt);
      dt.setDate(dt.getDate() + 1);
      dt.setHours(0);
      dt.setMinutes(0);
      dt.setSeconds(0);
      dt.setMilliseconds(-1);
      return dt;
    },

    _setConstraint: function(cal, dt) {
      var id = cal.get('id');
      var rules = {};
      var minDate = this.start.get('minimumDate');
      var maxDate = this.end.get('maximumDate');
      var i;

      if (this.timeGroup === 'year') {
        cal.navigator.set('shiftByMonths', 12);

        if (id === 'start') {
          rules['all'] = {
            '0': {
              '1': 'enabled_dates'
            }
          };
        } else {
          rules['all'] = {
            '11': {
              '31': 'enabled_dates'
            }
          };
        }
      } else if (this.timeGroup === 'quarter') {
        cal.navigator.set('shiftByMonths', 3);

        // 0,1 - 2,31 | 3,1 - 5,30 | 6,1 - 8,30 | 9,1 - 11,31
        if (id === 'start') {
          rules['all'] = {
            '0,3,6,9': {
              '1': 'enabled_dates'
            }
          };
        } else {
          rules['all'] = {
            '2,11': {
              '31': 'enabled_dates'
            },
            '5,8': {
              '30': 'enabled_dates'
            }
          };
        }
      } else if (this.timeGroup === 'month') {
        cal.navigator.set('shiftByMonths', 1);

        if (id === 'start') {
          rules['all'] = {
            'all': {
              '1': 'enabled_dates'
            }
          };
        } else {
          rules['all'] = {
            '0,2,4,6,7,9,11': {
              '31': 'enabled_dates'
            },
            '3,5,8,10': {
              '30': 'enabled_dates'
            }
          };

          // leap years
          var isLeapYear = function(yr) {
            return ((yr % 4 === 0) && (yr % 100 !== 0)) || (yr % 400 === 0);
          };

          for (i = minDate.getFullYear(); i <= maxDate.getFullYear(); i++) {
            if (isLeapYear(i)) {
              rules[i.toString()] = {
                '1': {
                  '29': 'enabled_dates'
                }
              };
            } else {
              rules[i.toString()] = {
                '1': {
                  '28': 'enabled_dates'
                }
              };
            }
          }
        }
      } /*else if (this.timeGroup === 'week') { // no further constraining for now...
        cal.navigator.set('shiftByMonths', 1);

        rules['all'] = {
          'all': {
            '0': 'enabled_dates'
          }
        };
      }*/ else {
        cal.navigator.set('shiftByMonths', 1);

        if (minDate.getFullYear() === maxDate.getFullYear()) {
          rules[minDate.getFullYear().toString()] = {};
          rules[minDate.getFullYear().toString()][minDate.getMonth().toString()] = {};
          rules[minDate.getFullYear().toString()][minDate.getMonth().toString()][minDate.getDate() + '-31'] = 'enabled_dates';

          rules[maxDate.getFullYear().toString()] = {};
          rules[maxDate.getFullYear().toString()][maxDate.getMonth().toString()] = {};
          rules[maxDate.getFullYear().toString()][maxDate.getMonth().toString()]['1-' + maxDate.getDate()] = 'enabled_dates';

          if (minDate.getMonth() !== maxDate.getMonth()) {
            rules[minDate.getFullYear().toString()][(minDate.getMonth() + 1) + '-' + (maxDate.getMonth() - 1)] = 'enabled_dates';
          }
        } else {
          for (i = minDate.getFullYear(); i <= maxDate.getFullYear(); i++) {
            if (i === minDate.getFullYear()) {
              rules[i.toString()] = {};
              rules[i.toString()][minDate.getMonth().toString()] = {};
              rules[i.toString()][minDate.getMonth().toString()][minDate.getDate() + '-31'] = 'enabled_dates';

              if (minDate.getMonth() < 11) {
                rules[i.toString()][(minDate.getMonth() + 1).toString() + '-11'] = 'enabled_dates';
              }
            } else if (i === maxDate.getFullYear()) {
              rules[i.toString()] = {};
              rules[i.toString()][maxDate.getMonth().toString()] = {};
              rules[i.toString()][maxDate.getMonth().toString()]['1-' + maxDate.getDate()] = 'enabled_dates';

              if (maxDate.getMonth() > 0) {
                rules[i.toString()]['0-' + (maxDate.getMonth() - 1).toString()] = 'enabled_dates';
              }
            } else {
              rules[i.toString()] = {
                'all': 'enabled_dates'
              };
            }
          }
        }
      }

      var today = new Date();
      if (!rules[today.getFullYear().toString()]) {
        rules[today.getFullYear().toString()] = {};
      }
      if (!rules[today.getFullYear().toString()][today.getMonth().toString()]) {
        rules[today.getFullYear().toString()][today.getMonth().toString()] = {};
      }
      rules[today.getFullYear().toString()][today.getMonth().toString()][today.getDate().toString()] = 'enabled_dates';

      if (id === 'start') {
        if (!rules[minDate.getFullYear().toString()]) {
          rules[minDate.getFullYear().toString()] = {};
        }
        if (!rules[minDate.getFullYear().toString()][minDate.getMonth().toString()]) {
          rules[minDate.getFullYear().toString()][minDate.getMonth().toString()] = {};
        }
        rules[minDate.getFullYear().toString()][minDate.getMonth().toString()][minDate.getDate().toString()] = 'enabled_dates';
      } else {
        if (!rules[maxDate.getFullYear().toString()]) {
          rules[maxDate.getFullYear().toString()] = {};
        }
        if (!rules[maxDate.getFullYear().toString()][maxDate.getMonth().toString()]) {
          rules[maxDate.getFullYear().toString()][maxDate.getMonth().toString()] = {};
        }
        rules[maxDate.getFullYear().toString()][maxDate.getMonth().toString()][maxDate.getDate().toString()] = 'enabled_dates';
      }

      cal.set('customRenderer', { rules: rules });

      if (id === 'start') {
        cal.set('maximumDate', this._convertMaxDate(dt));
      } else {
        cal.set('minimumDate', this._convertMinDate(dt));
      }
    },

    init: function() {
      var startDate = this._convertMinDate(new Date(new Date().setMonth(new Date().getMonth() - 1)));
      var endDate = this._convertMinDate(new Date());

      this.start.set('enabledDatesRule', 'enabled_dates');
      this._setConstraint(this.start, endDate);

      this.end.set('enabledDatesRule', 'enabled_dates');
      this._setConstraint(this.end, startDate);

      this.start.subtractMonth();

      this.start.selectDates(new Date(startDate));
      this.end.selectDates(new Date(endDate));

      function calSelectionChange(e) {
        var newDate = e.date,
            cal = e.currentTarget,
            id = cal.get('id'),
            prevMonth;

        if (!cal._canBeSelected(e.date)) {
          cal.selectDates(id === 'start' ? new Date(START_SELECTED_DATE) : new Date(END_SELECTED_DATE));
          return;
        }

        if (id === 'start') {
          this._setConstraint(this.end, newDate);

          prevMonth = this.end.get('date').getMonth();

          // force refresh of calendar styling
          this.end.addMonth();
          if (this.end.get('date').getMonth() !== prevMonth) {
            this.end.subtractMonth();
          }
        } else if (id === 'end') {
          this._setConstraint(this.start, newDate);

          prevMonth = this.start.get('date').getMonth();

          // force refresh of calendar styling
          this.start.addMonth();
          if (this.end.get('date').getMonth() !== prevMonth) {
            this.start.subtractMonth();
          }
        }

        Y.fire('visualizer:calendar_change', {
          id: id,
          dt: newDate
        });
      }

      function setNavLabel(e) {
        var label = e.currentTarget.get('parentNode').one('.yui3-calendar-header-label').getHTML();
        NAV_LABEL = label.substring(0, label.indexOf(' ')).toLowerCase();
      }

      function nextMonthNav(e, calId) {
        var disabled = e.currentTarget.getAttribute('aria-disabled');
        if (disabled === true || disabled === 'true') return;

        var cal = this[calId];
        var month = MONTH_NAMES.indexOf(NAV_LABEL);
        var adjustMonth;

        if (this.timeGroup === 'year') {
          if (calId === 'start' && month !== 0) {
            adjustMonth = function() {
              for (var i = 0; i < month; i++) {
                this.subtractMonth();
              }
            };
          } else if (calId === 'end' && month !== 11) {
            if (month !== 11) {
              adjustMonth = function() {
                for (var i = 0; i < month + 1; i++) {
                  this.subtractMonth();
                }
              };
            }
          }
        } else if (this.timeGroup === 'quarter') { // 0,1 - 2,31 | 3,1 - 5,30 | 6,1 - 8,30 | 9,1 - 11,31
          if (calId === 'start' && month !== 0 && month !== 3 && month !== 6 && month !== 9) {
            adjustMonth = function() {
              if (month % 3 === 1) {
                this.subtractMonth();
              } else if (month % 3 === 2) {
                this.subtractMonth();
                this.subtractMonth();
              }
            };
          } else if (calId === 'end' && month !== 2 && month !== 5 && month !== 8 && month !== 11) {
            adjustMonth = function() {
              if (month % 3 === 0) {
                this.subtractMonth();
              } else if (month % 3 === 1) {
                this.subtractMonth();
                this.subtractMonth();
              }
            };
          }
        }

        if (adjustMonth) {
          Y.later(50, cal, adjustMonth);
        }
      }

      function prevMonthNav(e, calId) {
        var disabled = e.currentTarget.getAttribute('aria-disabled');
        if (disabled === true || disabled === 'true') return;

        var cal = this[calId];
        var month = MONTH_NAMES.indexOf(NAV_LABEL);
        var adjustMonth;

        if (this.timeGroup === 'year') {
          if (calId === 'start' && month !== 0) {
            adjustMonth = function() {
              for (var i = 0; i < 12 - month; i++) {
                this.addMonth();
              }
            };
          } else if (calId === 'end' && month !== 11) {
            if (month !== 11) {
              adjustMonth = function() {
                for (var i = 0; i < 11 - month; i++) {
                  this.addMonth();
                }
              };
            }
          }
        } else if (this.timeGroup === 'quarter') { // 0,1 - 2,31 | 3,1 - 5,30 | 6,1 - 8,30 | 9,1 - 11,31
          if (calId === 'start' && month !== 0 && month !== 3 && month !== 6 && month !== 9) {
            adjustMonth = function() {
              if (month % 3 === 1) {
                this.addMonth();
                this.addMonth();
              } else if (month % 3 === 2) {
                this.addMonth();
              }
            };
          } else if (calId === 'end' && month !== 2 && month !== 5 && month !== 8 && month !== 11) {
            adjustMonth = function() {
              if (month % 3 === 0) {
                this.addMonth();
                this.addMonth();
              } else if (month % 3 === 1) {
                this.addMonth();
              }
            };
          }
        }

        if (adjustMonth) {
          Y.later(50, cal, adjustMonth);
        }
      }

      this.start.on('selectionChange', function(e) { START_SELECTED_DATE = e.newSelection[0]; }, this);
      this.end.on('selectionChange', function(e) { END_SELECTED_DATE = e.newSelection[0]; }, this);

      this.start.on('dateClick', calSelectionChange, this);
      this.end.on('dateClick', calSelectionChange, this);

      this.start.navigator._controls.nextMonth.before('selectstart', setNavLabel, this);
      this.start.navigator._controls.prevMonth.before('selectstart', setNavLabel, this);
      this.end.navigator._controls.nextMonth.before('selectstart', setNavLabel, this);
      this.end.navigator._controls.prevMonth.before('selectstart', setNavLabel, this);

      this.start.navigator._controls.nextMonth.after('click', nextMonthNav, this, 'start');
      this.start.navigator._controls.prevMonth.after('click', prevMonthNav, this, 'start');
      this.end.navigator._controls.nextMonth.after('click', nextMonthNav, this, 'end');
      this.end.navigator._controls.prevMonth.after('click', prevMonthNav, this, 'end');

      Y.one('body').on('click', function(e) {
        try { if (e.target.getHTML().toLowerCase() === 'custom' || e.target.ancestor(this.el)) return; } catch(err) {}

        this.toggleVisibility(false);
      }, this);
    },

    toggleVisibility: function(visible, alignNode, timeGroup, timeFrame, minDate, maxDate) {
      if (visible === false && this.node.hasClass(this.hidden)) {
        return;
      }

      if ( minDate ) {
        this.start.set('minimumDate', this._convertMinDate(minDate));
        this.end.set('minimumDate', this._convertMinDate(minDate));
      }
      if ( maxDate ) {
        this.start.set('maximumDate', this._convertMaxDate(maxDate));
        this.end.set('maximumDate', this._convertMaxDate(maxDate));
      }

      this.constrainDates(timeGroup, timeFrame);

      var transition = Y.bind(function transition(fadeIn) {
        if (fadeIn) {
          this.node.removeClass(this.hidden);
        }

        if (alignNode) {
          this.node.setStyle('top', alignNode.getY() - (parseInt(this.node.getComputedStyle('height'), 10) / 2));
        }

        this.node.transition({
          duration: 0.5,
          opacity: fadeIn ? 1 : 0
        }, Y.bind(function() {
          if (!fadeIn) {
            this.node.addClass(this.hidden);
          }
        }, this));
      }, this);

      if (Y.Lang.isUndefined(visible) || Y.Lang.isNull(visible)) {
        if (this.node.hasClass(this.hidden)) {
          transition(true);
        } else {
          transition(false);
        }
      } else if (visible) {
        transition(true);
      } else {
        transition(false);
      }
    },

    constrainDates: function(timeGroup, timeFrame) {
      if (!timeFrame) {
        timeFrame = {};
      }

      if (!timeFrame.start) {
        timeFrame.start = this.start.get('selectedDates')[0];
      }
      if (!timeFrame.end) {
        timeFrame.end = this.end.get('selectedDates')[0];
      }

      this.timeGroup = timeGroup;

      if (!timeFrame.start || !timeFrame.end) return;

      timeFrame.start = this._convertMinDate(timeFrame.start);
      timeFrame.end = this._convertMinDate(timeFrame.end);

      if (timeGroup === 'year') {
        timeFrame.start.setMonth(0);
        timeFrame.start.setDate(1);

        timeFrame.end.setMonth(11);
        timeFrame.end.setDate(31);
      } else if (timeGroup === 'quarter') {
        timeFrame.start.setDate(1);

        if (timeFrame.start.getMonth() < 3) {
          timeFrame.start.setMonth(0);
        } else if (timeFrame.start.getMonth() < 6) {
          timeFrame.start.setMonth(3);
        } else if (timeFrame.start.getMonth() < 9) {
          timeFrame.start.setMonth(6);
        } else {
          timeFrame.start.setMonth(9);
        }

        if (timeFrame.end.getMonth() < 3) {
          timeFrame.end.setMonth(2);
          timeFrame.end.setDate(31);
        } else if (timeFrame.end.getMonth() < 6) {
          timeFrame.end.setMonth(5);
          timeFrame.end.setDate(30);
        } else if (timeFrame.end.getMonth() < 9) {
          timeFrame.end.setMonth(8);
          timeFrame.end.setDate(30);
        } else {
          timeFrame.end.setMonth(11);
          timeFrame.end.setDate(31);
        }
      } else if (timeGroup === 'month') {
        if (timeFrame.start.getDate() !== 1) {
          timeFrame.start.setDate(1);
        }

        var lastDate = new Date(timeFrame.end.getFullYear(), timeFrame.end.getMonth() + 1, 0).getDate();
        if (timeFrame.end.getDate() !== 1 && timeFrame.end.getDate() !== lastDate) {
          timeFrame.end.setDate(lastDate);
        }
      } else if (timeGroup === 'week') {
        // TODO
      }

      this.updateDates(timeFrame);
    },

    updateDates: function(timeFrame) {
      if (timeFrame && timeFrame.start) {
        timeFrame.start = this._convertMinDate(timeFrame.start);

        var minDate = this.start.get('minimumDate');
        if (timeFrame.start < minDate) {
          timeFrame.start = this._convertMinDate(minDate);
        }

        this._setConstraint(this.end, timeFrame.start);
        this.start.deselectDates();
        this.start.selectDates(new Date(timeFrame.start));
        this.start.set('date', new Date(timeFrame.start));
      }

      if (timeFrame && timeFrame.end) {
        timeFrame.end = this._convertMinDate(timeFrame.end);

        var maxDate = this.end.get('maximumDate');
        if (timeFrame.end > maxDate) {
          timeFrame.end = this._convertMinDate(maxDate);
        }

        this._setConstraint(this.start, timeFrame.end);
        this.end.deselectDates();
        this.end.selectDates(new Date(timeFrame.end));
        this.end.set('date', new Date(timeFrame.end));
      }
    }
  };

  Y.Visualizer.Component.Calendars = Calendars;
}, '1.0', {
  requires: ['node', 'calendar', 'transition']
});

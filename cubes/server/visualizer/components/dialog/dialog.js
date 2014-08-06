YUI.add('visualizer-component-dialog', function (Y) {
  Y.namespace('Visualizer.Component');

  var CLASS_PREFIX = 'visualizer-component-dialog';

  // check if a variable exists (not null or undefined)
  function exists(v) {
    return !Y.Lang.isNull(v) && !Y.Lang.isUndefined(v);
  }

  var VizCompDialog = function(config) {
    this.parent = exists(config.parent) ? (typeof config.parent === 'string' ? Y.one('#' + config.parent) : Y.one(config.parent)) : Y.one('body');
    this.flyout = exists(config.flyout) ? config.flyout : null; // left, bottom, top, right // TODO: Support bottom, top, right
    this.id = exists(config.id) ? config.id : null;
    this.modal = exists(config.modal) ? config.modal : true;
    this.title = exists(config.title) ? config.title : null;
    this.icon = exists(config.icon) ? config.icon : null;
    this.description = exists(config.description) ? config.description : null;
    this.fields = exists(config.fields) ? (Y.Lang.isArray(config.fields) ? config.fields : [config.fields]) : null;
    this.cancelButton = exists(config.cancelButton) ? config.cancelButton : true;
    this.buttons = exists(config.buttons) ? (Y.Lang.isArray(config.buttons) ? config.buttons : [config.buttons]) : null;

    this.node = null;
    this.wrapper = null;
    this.spinnerModal = null;
    this.spinner = null;
    this.modalNode = null;

    this.init();

    this.render();
  };

  VizCompDialog.prototype = {
    _addHeader: function() {
      if (!exists(this.title) && !exists(this.description)) return;

      var header = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-header');
      this.wrapper.append(header);

      var iconNode, titleNode, descNode;
      if (exists(this.icon)) {
        iconNode = Y.Node.create('<img>')
          .addClass(CLASS_PREFIX + '-header-icon')
          .setAttribute('src', this.icon);
        header.append(iconNode);
      }

      if (exists(this.title)) {
        titleNode = Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-header-title')
          .setHTML(this.title);
        header.append(titleNode);
      }

      if (exists(this.description)) {
        descNode = Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-header-description')
          .setHTML(this.description);
        header.append(descNode);
      }

      return header;
    },

    _addContent: function() {
      if (!exists(this.fields)) return;

      var k, fieldValue, cbBlock;

      var content = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content');

      for (var i = 0; i < this.fields.length; i++) {
        this._addColumn(this.fields[i], content);
      }

      this.wrapper.append(content);
    },

    _replaceContent: function() {
      var content = this.wrapper.one('.' + CLASS_PREFIX + '-content');
      content.empty();

      for (var i = 0; i < this.fields.length; i++) {
        this._addColumn(this.fields[i], content);
      }
    },

    _addColumn: function(column, node) {
      if (!node) {
        node = this.wrapper.one('.' + CLASS_PREFIX + '-content');
      }

      var columnBlockNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-column-block');

      var i;

      if (!Y.Lang.isArray(column)) {
        column = [column];
      }

      for (i = 0; i < column.length; i++) {
        var field = column[i];

        var block = this._buildBlock(field, column.length === 1);
        columnBlockNode.append(block);
      }

      node.append(columnBlockNode);
    },

    _buildBlock: function(field, singleColumn) {
      var blockWrapper = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-block-wrapper');
      var block = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-block');
      blockWrapper.append(block);

      block.setData('type', field.type);

      if (singleColumn) {
        blockWrapper.addClass(CLASS_PREFIX + '-content-block-wrapper-single-column');
      }

      if (field.id) {
        block.setAttribute('id', field.id);
      }

      if (field.width) {
        block.setStyle('width', field.width);
      }

      if (field.styles) {
        blockWrapper.setStyles(field.styles);
      }

      if (field.label && field.type !== 'checkbox' && field.type !== 'button') {
        block.append(Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-content-label')
          .setHTML(field.label)
        );
      }

      if (field.type === 'dropdown') {
        var ddWrapperNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-dd-wrapper');
        var ddDisplayWrapperNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-dd-display-wrapper');
        var ddDisplayNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-dd-display');
        var ddNode = Y.Node.create('<select>').addClass(CLASS_PREFIX + '-content-dd');
        var defaultLabel;
        var defaultValue;

        ddNode.on('change', function(e) {
          var node = e.currentTarget;
          var newVal = node.get('value');
          var displayLabel = null;

          for (var i = 0; i < field.values.length; i++) {
            var val = field.values[i];
            if (Y.Lang.isObject(val)) {
              if (!exists(val.value) && !exists(val.label)) continue;

              if (exists(val.value) && val.value === newVal) {
                displayLabel = exists(val.label) ? val.label : val.value;
                break;
              } else if (!exists(val.value) && val.label === newVal) {
                displayLabel = val.label;
                break;
              }
            }
          }

          node.get('parentNode').one('.' + CLASS_PREFIX + '-content-dd-display')
            .setHTML(displayLabel ? displayLabel : newVal);

          var prevVal = field.value;
          field.value = newVal;

          if (field.on && field.on.change) {
            field.on.change(newVal, displayLabel ? displayLabel : newVal, prevVal);
          }
        }, this);

        if (field.values) {
          if (!Y.Lang.isArray(field.values)) {
            field.values = [field.values];
          }

          if (!exists(field.allowEmpty) || field.allowEmpty) {
            ddNode.append(Y.Node.create('<option>').setAttribute('value', '').setHTML('&nbsp;'));
          }

          for (k = 0; k < field.values.length; k++) {
            fieldValue = field.values[k];
            var opt = Y.Node.create('<option>');

            if (Y.Lang.isObject(fieldValue)) {
              if (!exists(fieldValue.value) && !exists(fieldValue.label)) continue;

              if (exists(fieldValue.value)) {
                if ((!field.value && !exists(defaultValue) && exists(field.allowEmpty) && !field.allowEmpty) ||
                  (field.value && field.value === fieldValue.value))
                {
                  defaultLabel = exists(fieldValue.label) ? fieldValue.label : fieldValue.value;
                  defaultValue = fieldValue.value;

                  opt.setAttribute('selected', true);
                }

                opt.setAttribute('value', fieldValue.value);
                opt.setHTML(exists(fieldValue.label) ? fieldValue.label : fieldValue.value);
              } else {
                if ((!field.value && !exists(defaultValue) && exists(field.allowEmpty) && !field.allowEmpty) ||
                  (field.value && field.value === fieldValue.label))
                {
                  defaultLabel = fieldValue.label;
                  defaultValue = fieldValue.label;

                  opt.setAttribute('selected', true);
                }

                opt.setAttribute('value', fieldValue.label);
                opt.setHTML(fieldValue.label);
              }
            } else {
              if ((!field.value && !exists(defaultValue) && exists(field.allowEmpty) && !field.allowEmpty) ||
                (field.value && field.value === fieldValue))
              {
                defaultLabel = fieldValue;
                defaultValue = fieldValue;

                opt.setAttribute('selected', true);
              }

              opt.setAttribute('value', fieldValue);
              opt.setHTML(fieldValue);
            }

            ddNode.append(opt);
          }
        }

        if (field.value) {
          ddDisplayNode.setHTML(defaultLabel ? defaultLabel : field.value);
        } else if (exists(field.allowEmpty) && !field.allowEmpty) {
          ddDisplayNode.setHTML(defaultLabel ? defaultLabel : defaultValue);
        }

        ddDisplayWrapperNode.append(ddDisplayNode);
        ddWrapperNode.append(ddDisplayWrapperNode);
        ddWrapperNode.append(ddNode);
        block.append(ddWrapperNode);
      } else if (field.type === 'checkbox') {
        if (!exists(field.value) && !exists(field.label)) return;

        cbBlock = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-checkbox-block');

        cbBlock.append(Y.Node.create('<input>')
          .addClass(CLASS_PREFIX + '-content-checkbox')
          .setAttribute('type', 'checkbox')
          .setAttribute('value', exists(field.value) ? field.value : field.label)
        );

        cbBlock.append(Y.Node.create('<label>')
          .addClass(CLASS_PREFIX + '-content-checkbox-label')
          .setHTML(exists(field.label) ? field.label : field.value)
        );

        block.append(cbBlock);
      } else if (field.type === 'checkbox-group') {
        var cbGroupNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-checkbox-group');

        if (field.values) {
          if (!Y.Lang.isArray(field.values)) {
            field.values = [field.values];
          }

          for (k = 0; k < field.values.length; k++) {
            fieldValue = field.values[k];
            cbBlock = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-checkbox-block');

            if (!exists(field.inline) || field.inline) {
              cbBlock.addClass(CLASS_PREFIX + '-content-checkbox-block-inline');
            }

            var cb = Y.Node.create('<input>')
              .addClass(CLASS_PREFIX + '-content-checkbox')
              .setAttribute('type', 'checkbox');
            var label = Y.Node.create('<label>')
              .addClass(CLASS_PREFIX + '-content-checkbox-label');

            cbBlock.append(cb);
            cbBlock.append(label);

            if (Y.Lang.isObject(fieldValue)) {
              if (!exists(fieldValue.value) && !exists(fieldValue.label)) continue;

              if (exists(fieldValue.value)) {
                cb.setAttribute('value', fieldValue.value);
                label.setHTML(exists(fieldValue.label) ? fieldValue.label : fieldValue.value);
              } else {
                cb.setAttribute('value', fieldValue.label);
                label.setHTML(fieldValue.label);
              }

              if (fieldValue.checked) {
                cb.setAttribute('checked', fieldValue.checked);
              }
            } else {
              cb.setAttribute('value', fieldValue);
              label.setHTML(fieldValue);
            }

            cbGroupNode.append(cbBlock);
          }
        }

        block.append(cbGroupNode);
      } else if (field.type === 'button') {
        var btn = Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-btn');

        if (exists(field.label)) {
          btn.setHTML(field.label);
        }

        if (field.inverted) {
          btn.addClass(CLASS_PREFIX + '-btn-inverted');
        }

        if (!exists(field.styled) || field.styled) {
          btn.addClass(CLASS_PREFIX + '-btn-styled');
        }

        if (field.on && field.on.click) {
          btn.on('click', field.on.click, this);
        }

        block.append(btn);
      } else if (field.type === 'information') {
        var info = Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-content-information')
          .setHTML(field.value);

        if (field.center) {
          blockWrapper.addClass(CLASS_PREFIX + '-content-block-wrapper-centered');
        }

        block.append(info);
      } else { // textbox
        var textWrapperNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-content-text-wrapper');
        var textNode = Y.Node.create('<input>')
          .addClass(CLASS_PREFIX + '-content-text')
          .setAttribute('type', 'text');

        if (field.value) {
          textNode.setAttribute('value', field.value);
        }

        textNode.on('valuechange', function(e) {
          field.value = e.newVal;

          if (field.on && field.on.valuechange) {
            field.on.valuechange(e.newVal);
          }
        });

        textNode.on('change', function(e) {
          if (field.on && field.on.change) {
            field.on.change(e.currentTarget.get('value'));
          }
        });

        textWrapperNode.append(textNode);
        block.append(textWrapperNode);
      }

      if (field.description) {
        block.append(Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-content-description')
          .setHTML(field.description)
        );
      }

      return blockWrapper;
    },

    _addFooter: function() {
      if (!exists(this.buttons) && !this.cancelButton) return;

      var footer = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-footer');
      this.wrapper.append(footer);

      if (this.cancelButton) {
        var cancelBtnNode = Y.Node.create('<div>')
          .addClass(CLASS_PREFIX + '-btn')
          .setHTML('Cancel');

        cancelBtnNode.on('click', function() {
          this.close();
        }, this);

        footer.append(cancelBtnNode);
      }

      if (this.buttons) {
        for (var i = 0; i < this.buttons.length; i++) {
          var btn = this.buttons[i];

          var btnNode = Y.Node.create('<div>')
            .addClass(CLASS_PREFIX + '-btn');

          if (exists(btn.label)) {
            btnNode.setHTML(btn.label);
          }

          if (btn.inverted) {
            btnNode.addClass(CLASS_PREFIX + '-btn-inverted');
          }

          if (!exists(btn.styled) || btn.styled) {
            btnNode.addClass(CLASS_PREFIX + '-btn-styled');
          }

          if (exists(btn.click)) {
            btnNode.on('click', btn.click);
          }

          footer.append(btnNode);
        }
      }

      return footer;
    },

    init: function() {
      if (this.modal) {
        this.modalNode = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-modal');
        this.parent.append(this.modalNode);
      }

      this.node = Y.Node.create('<div>').addClass(this.flyout ? CLASS_PREFIX + '-flyout' : CLASS_PREFIX);
      if (exists(this.id)) this.node.setAttribute('id', this.id);

      this.wrapper = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-wrapper');
      this.node.append(this.wrapper);

      this.spinner = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-spinner').setStyle('display', 'none');
      for (var i = 1; i <= 5; i++) {
        this.spinner.append(Y.Node.create('<div>').addClass('rect' + i));
      }
      this.spinnerModal = Y.Node.create('<div>').addClass(CLASS_PREFIX + '-modal').setStyle('display', 'none');
      this.wrapper.append(this.spinnerModal);
      this.wrapper.append(this.spinner);

      this.parent.append(this.node);

      Y.later(100, this, function() {
        this.node.on('mousedownoutside', function() {
          this.close();
        }, this);
      });
    },

    render: function() {
      this._addHeader();
      this._addContent();
      this._addFooter();
    },

    addField: function(insertField, node, where) {
      if (!exists(node)) {
        this.fields.push(insertField);
        this._addColumn(insertField);
      } else {
        for (var i = 0; i < this.fields.length; i++) {
          if (Y.Lang.isArray(this.fields[i])) {
            var inserted = false;
            for (var k = 0; k < this.fields[i].length; k++) {
              if (this.fields[i][k].id === node) {
                this.fields[i].splice(where === 'after' ? k + 1 : k, 0, insertField);
                inserted = true;
                break;
              }
            }
            if (inserted) break;
          } else {
            if (this.fields[i].id === node) {
              this.fields.splice(where === 'after' ? i + 1 : i, 0, insertField);
              break;
            }
          }
        }

        this._replaceContent();
      }
    },

    replaceField: function(id, insertField) {
      if (!exists(id)) return;

      for (var i = 0; i < this.fields.length; i++) {
        if (Y.Lang.isArray(this.fields[i])) {
          var inserted = false;
          for (var k = 0; k < this.fields[i].length; k++) {
            if (this.fields[i][k].id === id) {
              this.fields[i] = insertField;
              inserted = true;
              break;
            }
          }
          if (inserted) break;
        } else {
          if (this.fields[i].id === id) {
            this.fields[i] = insertField;
            break;
          }
        }
      }

      this._replaceContent();
    },

    removeField: function(id) {
      if (!exists(id)) return;

      for (var i = 0; i < this.fields.length; i++) {
        if (Y.Lang.isArray(this.fields[i])) {
          var found = false;
          for (var k = 0; k < this.fields[i].length; k++) {
            if (this.fields[i][k].id === id) {
              this.fields[i].splice(k, 1);
              found = true;
              break;
            }
          }
          if (found) break;
        } else {
          if (this.fields[i].id === id) {
            this.fields.splice(i, 1);
            break;
          }
        }
      }

      this._replaceContent();
    },

    removeFields: function(id, where) {
      for (var i = 0; i < this.fields.length; i++) {
        if (Y.Lang.isArray(this.fields[i])) {
          var found = false;
          for (var k = 0; k < this.fields[i].length; k++) {
            if (this.fields[i][k].id === id) {
              if (where === 'after') {
                this.fields[i] = this.fields[i].slice(0, k + 1);
                this.fields = this.fields.slice(0, i + 1);
              }
              found = true;
              break;
            }
          }
          if (found) break;
        } else {
          if (this.fields[i].id === id) {
            if (where === 'after') {
              this.fields = this.fields.slice(0, i + 1);
            }
            break;
          }
        }
      }

      this._replaceContent();
    },

    getField: function(id) {
      var node = this.wrapper.one('#' + id);
      if (!node) return;

      var type = node.getData('type');

      if (type === 'dropdown') {
        return node.one('.' + CLASS_PREFIX + '-content-dd');
      } else if (type === 'checkbox') {
        return node.one('.' + CLASS_PREFIX + '-content-checkbox');
      } else if (type === 'checkbox-group') {
        return node.one('.' + CLASS_PREFIX + '-content-checkbox-group');
      } else if (type === 'button') {
        return node.one('.' + CLASS_PREFIX + '-btn');
      } else if (type === 'information') {
        return node.one('.' + CLASS_PREFIX + '-content-information');
      } else { //text
        return node.one('.' + CLASS_PREFIX + '-content-text');
      }
    },

    updateFieldValue: function(id, value) {
      if (!exists(id)) return;

      for (var i = 0; i < this.fields.length; i++) {
        if (Y.Lang.isArray(this.fields[i])) {
          var found = false;
          for (var k = 0; k < this.fields[i].length; k++) {
            if (this.fields[i][k].id === id) {
              this.fields[i][k].value = value;
              found = true;
              break;
            }
          }
          if (found) break;
        } else {
          if (this.fields[i].id === id) {
            this.fields[i].value = value;
            break;
          }
        }
      }

      this._replaceContent();
    },

    close: function() {
      if (this.modalNode) this.modalNode.remove(true);
      this.node.remove(true);
    },

    setLoadingState: function(loading) {
      if (loading === true) {
        this.spinnerModal.setStyle('display', null);
        this.spinner.setStyle('display', null);
      } else if (loading === false) {
        this.spinnerModal.setStyle('display', 'none');
        this.spinner.setStyle('display', 'none');
      } else {
        if (spinner.getStyle('display')) {
          this.spinnerModal.setStyle('display', null);
          this.spinner.setStyle('display', null);
        } else {
          this.spinnerModal.setStyle('display', 'none');
          this.spinner.setStyle('display', 'none');
        }
      }
    },

    set: function(prop, val) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      this[prop] = val;

      return this[prop];
    },

    get: function(prop) {
      if (Y.Lang.isUndefined(prop) || Y.Lang.isNull(prop)) return;

      return this[prop];
    }
  };

  Y.Visualizer.Component.Dialog = VizCompDialog;
}, '1.0', {
  requires: ['node', 'event-valuechange', 'event-outside']
});

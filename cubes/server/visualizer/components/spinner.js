YUI.add('visualizer-component-spinner', function (Y) {
  Y.namespace('Visualizer.Component');

  var VizCompSpinner = function(config) {
    this.spinner = new Spinner({ className: config.className });
    this.parent = Y.one(config.parent || 'body');
    this.modal = config.modal ? Y.one(config.modal) : null;
    this.hiddenEl = config.hidden;
  };

  VizCompSpinner.prototype = {
    _toggleModal: function(visible) {
      if (Y.Lang.isUndefined(this.modal) || Y.Lang.isNull(this.modal)) {
        return;
      }

      if (Y.Lang.isUndefined(visible) || Y.Lang.isNull(visible)) {
        this.modal.toggleClass(this.hiddenEl);
      } else if (visible) {
        this.modal.removeClass(this.hiddenEl);
      } else {
        this.modal.addClass(this.hiddenEl);
      }
    },

    spin: function() {
      this._toggleModal(true);
      this.spinner.spin(this.parent.getDOMNode());
    },

    stop: function() {
      this._toggleModal(false);
      this.spinner.stop();
    }
  };

  Y.Visualizer.Component.Spinner = VizCompSpinner;
}, '1.0', {
  requires: ['node']
});

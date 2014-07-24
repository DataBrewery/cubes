YUI({
  modules: {
    'visualizer-component-dropdown': {
      fullpath: 'components/dropdown/dropdown.js'
    },
    'visualizer-component-dialog': {
      fullpath: 'components/dialog/dialog.js'
    },
    'visualizer-component-spinner': {
      fullpath: 'components/spinner.js'
    },
    'visualizer-component-calendars': {
      fullpath: 'components/calendars.js'
    },
    'visualizer-nav': {
      fullpath: 'src/nav.js'
    },
    'visualizer-datasource-cubes': {
      fullpath: 'datasources/cubes.js'
    },
    'visualizer-datalayer': {
      fullpath: 'src/datalayer.js'
    },
    'visualizer-display': {
      fullpath: 'src/display.js'
    }
  }
}).use('node', 'router', 'querystring', 'event-resize', 'event-key', 'gallery-y64', 'transition', 'cookie', 'get',
  'visualizer-component-dialog', 'visualizer-component-spinner',
  'visualizer-datasource-cubes', 'visualizer-nav', 'visualizer-datalayer',
  function (Y)
{
  var WITHIN_PAGE_LOAD = true;
  var SPLASH_SCREEN = VisualizerConfig.splashScreen;

  var Spinner = new Y.Visualizer.Component.Spinner({
    className: 'spinner',
    modal: '.modal',
    parent: '.content',
    hidden: 'hidden'
  });
  var DataSource = new Y.Visualizer.DataSource.Cubes();
  var Nav = new Y.Visualizer.Nav(DataSource);
  var Router;

  Y.all('.logo-img').setStyle('background-image', 'url(' + VisualizerConfig.logo.img + ')');
  Y.all('.logo-txt').setHTML(VisualizerConfig.logo.text);

  if (VisualizerConfig.loadExtra) {
    var cssFiles = VisualizerConfig.loadExtra.css;

    if (!cssFiles) cssFiles = [];
    if (!Y.Lang.isArray(cssFiles)) cssFiles = [cssFiles];

    Y.Get.css(cssFiles);
  }

  function getUrlParams() {
    var qs = '';

    if (window.location.href.indexOf('?') !== -1) {
      qs = window.location.href.substring(window.location.href.indexOf('?') + 1);
    }

    qs = Y.QueryString.parse(qs);

    if (qs.layers) {
      var layers = qs.layers.split(',');
      for (var i = 0; i < layers.length; i++) {
        layers[i] = Y.Y64.decode(layers[i]);
      }
    }

    return qs;
  }

  function error(msg) {
    var node = Y.one('.content');
    node.empty();

    if (msg) {
      var wrapper = Y.Node.create('<div>').addClass('center-block error');
      var content = Y.Node.create('<div>').addClass('centered').setHTML(msg);
      wrapper.append(content);
      node.append(wrapper);
    }
  }

  function updateConnectionInfo() {
    var info = DataSource.get('info');

    var label = info ? (info.label ? info.label : info.url) : null;
    if (info && info.authentication && info.authentication.identity) {
      label += " (as " + info.authentication.identity + ")";
    }
    var desc = info ? info.description : null;

    Y.one('.sidebar .connection-info .text').setHTML(label);
    Y.one('.sidebar .connection-info .tooltip .url').setHTML(info ? info.url : '');
    Y.one('.sidebar .connection-info .tooltip .description').setHTML(desc);

    if (!label) {
      Y.one('.sidebar .connection-info').addClass('hidden');
    } else {
      Y.one('.sidebar .connection-info').removeClass('hidden');

      if (info && info.description) {
        Y.one('.sidebar .connection-info .tooltip').setStyle('margin-top', '-17px');
      } else {
        Y.one('.sidebar .connection-info .tooltip').setStyle('margin-top', '-10px');
      }
    }
  }

  function buildURL(replace) {
    var config = Nav.generateSimpleConfig();

    var useConfig = false;
    for (var opt in config) {
      if (opt === 'layers') {
        if (!Y.Lang.isUndefined(config[opt]) && !Y.Lang.isNull(config[opt])) {
          for (var i = 0; i < config[opt].length; i++) {
            var layer = config[opt][i];

            for (var layerOpt in layer) {
              if (!Y.Lang.isUndefined(layer[layerOpt]) && !Y.Lang.isNull(layer[layerOpt])) {
                useConfig = true;
                break;
              }
            }

            if (useConfig) {
              break;
            }
          }
        }
      } else if (Y.Lang.isObject(config[opt])) {
        for (var innerOpt in config[opt]) {
          if (!Y.Lang.isUndefined(config[opt][innerOpt]) && !Y.Lang.isNull(config[opt][innerOpt])) {
            useConfig = true;
            break;
          }
        }
      } else if (!Y.Lang.isUndefined(config[opt]) && !Y.Lang.isNull(config[opt])) {
        useConfig = true;
        break;
      }
    }

    var url;
    if (useConfig) {
      if (VisualizerConfig.debug) {
        console.debug('URL CONFIG:', config);
      }

      var json = JSON.stringify(config);
      var encoded = Y.Y64.encode(json);
      url = encoded !== '' ? ('?config=' + encoded) : '';
    } else {
      url = '';
    }

    WITHIN_PAGE_LOAD = true;

    if (replace) {
      Router.replace(url);
    } else {
      Router.save(url);
    }

    if (VisualizerConfig.on && VisualizerConfig.on.urlUpdate) {
      VisualizerConfig.on.urlUpdate(url);
    }
  }

  Y.on('visualizer:nav_change', function(ignoreLoad, ignoreURLUpdate) {
    if (!ignoreURLUpdate) {
      buildURL();
    }

    if (ignoreLoad) {
      Nav.render(null, true);
    } else {
      Spinner.spin();

      DataSource.load(Nav.generateSimpleConfig(), function(data) {
        Spinner.stop();
        Nav.render(data);
      }, function(resp) {
        Spinner.stop();
        var errorText;
        if (resp.statusText === 'abort') {
          error('Data Source request aborted!');
        } else {
          error('Error retrieving data from the Data Source.');
        }
      });
    }
  });

  Y.on('visualizer:annotate:update', function() {
    buildURL(true);
  });

  Y.on('visualizer:empty_data', function() {
    error('No results found.');
  });

  Y.on('visualizer:logout', function() {
    // document.location.href = '/cubes/logout?url=' + encodeURIComponent(window.document.location);
    SPLASH_SCREEN = VisualizerConfig.splashScreen;
    DataSource.disconnect();
    updateConnectionInfo();
    Nav.fullReset();
  });

  Y.on('windowresize', function() {
    Nav.resize();
  });

  Y.one('window').on('key', function() {
    if (DataSource.isInProgress()) {
      DataSource.abort();

      var dialog = new Y.Visualizer.Component.Dialog({
        id: 'abort-dialog',
        title: 'Aborted',
        icon: 'images/warning-icon-color.png',
        fields: [{
          type: 'information',
          center: true,
          value: 'Request aborted!'
        }],
        cancelButton: false,
        buttons: [{
          label: 'Retry',
          click: function() {
            Nav.load();
            dialog.close();
          }
        }, {
          label: 'Reset',
          click: function() {
            Nav.fullReset();
            dialog.close();
          }
        }, {
          label: 'Logout',
          click: function() {
            Y.fire('visualizer:logout');
            dialog.close();
          }
        }]
      });
    }
  }, 'esc');

  Router = new Y.Router({
    html5: false,
    root: VisualizerConfig.root,
    routes: [{
        path: '*',
        callbacks: function() {
          var encoded = getUrlParams()['config'];
          var config;

          if (encoded) {
            var decoded = Y.Y64.decode(encoded);
            config = JSON.parse(decoded);
          }

          if (config && config.datasource) {
            SPLASH_SCREEN = false;
          }

          function pageLoad() {
            DataSource.set('url', config && config.datasource ? config.datasource : VisualizerConfig.cubesUrl);
            DataSource.set('debug', VisualizerConfig.debug);

            if (!DataSource.isConnected()) {
              Spinner.spin();

              DataSource.connect(function() {
                Spinner.stop();
                updateConnectionInfo();
                error();
                Nav.build(config);
              }, function() {
                Spinner.stop();
                updateConnectionInfo();
                error('Unable to connect to Data Source at ' + DataSource.get('url'));
              });
            } else if (WITHIN_PAGE_LOAD) {
              WITHIN_PAGE_LOAD = false;
            } else if (!WITHIN_PAGE_LOAD) {
              Nav.build(config);
            }
          }

          function splashScreenContinue() {
            var cubesUrl = Y.one('.splash-screen .cubes-url input').get('value');

            if (!cubesUrl || cubesUrl === '') {
              // TODO: alert, don't allow
            } else {
              if ( ! /^https?:\/\//.test(cubesUrl)) {
                cubesUrl = 'http://' + cubesUrl;
              }

              Y.Cookie.set('visualizer_cubes_url', cubesUrl);
              VisualizerConfig.cubesUrl = cubesUrl;
              VisualizerConfig.debug = Y.one('.splash-screen .debug input').get('checked');

              Y.one('.splash-screen').transition({
                easing: 'ease-out',
                duration: 0.75,
                opacity: 0
              }, function() {
                this.addClass('hidden');
                Y.one('body').setStyle('overflow', 'auto');
                SPLASH_SCREEN = false;
                pageLoad();
              });
            }
          }

          if (SPLASH_SCREEN) {
            Y.one('.splash-screen').removeClass('hidden');
            Y.one('.splash-screen').setStyle('opacity', 1);
            Y.one('body').setStyle('overflow', 'hidden');

            var cubesUrl = Y.Cookie.get('visualizer_cubes_url');
            if (!cubesUrl) {
              cubesUrl = VisualizerConfig.cubesUrl;

              if (!cubesUrl) {
                cubesUrl = Y.visualizer.Config.defaultCubesUrl;
              }
            }

            Y.one('.splash-screen .cubes-url input').set('value', cubesUrl);
            Y.one('.splash-screen .debug input').set('checked', VisualizerConfig.debug);

            Y.one('.load-overlay').addClass('hidden');

            Y.one('.splash-screen .cubes-url input').on('key', splashScreenContinue, 'enter');
            Y.one('.splash-screen .cubes-url .text-btn').on('click', function() {
              Y.one('.splash-screen .cubes-url input').set('value', VisualizerConfig.defaultCubesUrl);
            });
            Y.one('.splash-screen .btn').on('click', splashScreenContinue);
          } else {
            Y.one('.splash-screen').addClass('hidden');
            Y.one('body').setStyle('overflow', 'auto');
            Y.one('.load-overlay').addClass('hidden');
            pageLoad();
          }
        }
      }
    ]
  }).dispatch();
});

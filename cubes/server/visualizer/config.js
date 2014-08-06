var VisualizerConfig = {
  logo: {
    img: 'images/logo.png',
    text: 'Cubes Visualizer'
  },
  splashScreen: true,
  cubesUrl: window.location.href.substring(0, window.location.href.indexOf('visualizer')),
  defaultCubesUrl: window.location.href.substring(0, window.location.href.indexOf('visualizer')),
  debug: false,
  root: '/',
  yuiLocation: 'http://yui.yahooapis.com/3.15.0/build/yui/yui-min.js',
  yuiConfigLocation: null,
  loadExtra: { // order matters!
    css: [],
    js: []
  },
  on: {
    urlUpdate: function(url) {}
  }
};

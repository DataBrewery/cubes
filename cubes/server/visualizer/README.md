Cubes Visualizer
================

Config
======

All configuration that should be needed will be in [config.js](https://github.com/rberlew/cubes-visualizer/blob/master/config.js).

#### Logo and Title ####
*img* : Logo image location. (Default: cubes logo)<br>
*text* : Specialized page title. (Default: Cubes Visualizer)

`logo: {
  img: 'images/logo.png',
  text: 'Cubes Visualizer'
}`

#### Splash Screen ####
*splashScreen* : Set to false to disable the splash screen. (Default: true)

`splashScreen: true`

#### Cubes URL ####
*cubesUrl* : URL for your cubes service. (Default: public cubes demo)<br>
*defaultCubesUrl* : Default Cubes URL to fall back to. (Default: public cubes demo)

`cubesUrl: 'http://slicer-demo.databrewery.org/'`

#### Debug ####
*debug* : Set to true to enable debugging. (Default: false)

`debug: false`

#### Root ####
*root* : Root used for YUI Router. (Default: '/')

`root: '/'`

#### YUI Location ####
*yuiLocation* : Location of YUI. (Default: public YUI url)<br>
*yuiConfigLocation* : Location of YUI config file. (Default: empty)

`yuiLocation: 'http://yui.yahooapis.com/3.15.0/build/yui/yui-min.js'`<br>
`yuiConfigLocation: null`

#### Load Extra JS/CSS Files ####
*css* : Array of css file locations. (Default: empty array)<br>
*js* : Array of js file locations. (Default: empty array)<br>
**Order matters!**

`loadExtra: {
  css: [],
  js: []
}`

#### Events ####
*urlUpdate* : Function to run when the visualizer URL changes. Receives new URL as parameter. (Default: empty function)

`on: {
  urlUpdate: function(url) {}
}`

License
=======

Cubes is licensed under MIT license with following addition:

    If your version of the Software supports interaction with it remotely 
    through a computer network, the above copyright notice and this permission 
    notice shall be accessible to all users.

Simply said, that if you use it as part of software as a service (SaaS) you 
have to provide the copyright notice in an about, legal info, credits or some 
similar kind of page or info box.

For full license see the LICENSE file.
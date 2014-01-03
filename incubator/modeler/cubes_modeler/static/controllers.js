// Controllers for Cubes Modeler Application
//

var ModelerControllers = angular.module('ModelerControllers', []);

// TODO: use "content" concept everywhere where possible

PhysicalObject = function($scope){
    // Joins
    // =====

    $scope.jsonEdited = function() {
        try {
            JSON.parse($scope.content.jsonString);
            $scope.jsonIsValid = true;
        }
        catch(err) {
            $scope.jsonIsValid = false;
            $scope.jsonError = err.message;
        };
    };
}

CubesModelerApp.directive("jsonEditor", function() {
    return {
        templateUrl: 'views/partials/json_editor.html',
        require: "ngModel",
        scope: {
            jsonObject: "=ngModel",
            foo: "@"
        },
        link: function($scope, $element, $attrs) {
            $scope.jsonString = JSON.stringify($scope.jsonObject, null, "    ")
            $scope.jsonIsValid = true;
            console.debug("linking json editor")
            console.debug($scope.foo)

            $scope.jsonEdited = function() {
                if($scope.jsonString == "") {
                    $scope.jsonObject = null;
                    $scope.jsonIsValid = true;
                }
                else {
                    try {
                        obj = JSON.parse($scope.jsonString);
                        $scope.jsonObject = obj;
                        $scope.jsonIsValid = true;
                    }
                    catch(err) {
                        $scope.jsonIsValid = false;
                        $scope.jsonError = err.message;
                    };
                };
            };
        }
    }
});


CubesModelerApp.directive("mappingEditor", function() {
    return {
        templateUrl: 'views/partials/mapping.html',
        restrict: 'E',
        require: "ngModel",
        scope: {
            content: "=ngModel",
        },
        link: function($scope, $element, $attrs) {
            $scope.storeType = $scope.$parent.storeType;

            // Keep the type if we have an editor for it, otherwise default
            // JSON editor will be used
            if($scope.$parent.mappingEditors.indexOf($scope.storeType) == -1) {
                $scope.storeType = null;
            }

            $scope.isAttributeMapping = true;
        }
    }
});


ModelerControllers.controller('ModelController', ['$rootScope', '$scope', '$http', '$q',
    function ($rootScope, $scope, $http, $q) {
        var cubes = $http.get('cubes');
        var dimensions = $http.get('dimensions');
        var model = $http.get('model');

        $rootScope.advancedInterface = true;
        $scope.foo = "bar";
        $rootScope.setInterfaceType = function(ifaceType) {
            $rootScope.advancedInterface = (ifaceType == "advanced");
        }

        $q.all([cubes, dimensions, model]).then(function(results){
            console.log("Loading model...");
            console.debug("scope: " + $scope.$id);

            $scope.cubes = results[0].data;
            $scope.dimensions = results[1].data;
            $scope.model = results[2].data;

            $scope.info = $scope.model.info || {}
            $scope.browser_options = $scope.model.browser_options || {}

            options = $scope.model["__modeler_options__"] || {}
            $rootScope.modelOptions = options
            $rootScope.storeType = options.store_type

            var mappings = $scope.model.mappings

            if(!mappings){
                console.debug("No model mappings.")
                mappings = {}
            };
            console.debug(mappings)
            // Convert mappings into a list
            $scope.mappings = [];
            for(var key in mappings) {
                value = mappings[key];
                mapping = {
                    "key": key,
                    "value": mappings[key]
                };
                if(_.isString(value)) {
                    mapping["string"] = value;
                    mapping["type"] = "string";
                };
                mapping["jsonString"] = JSON.stringify(value, null, "    ");
                $scope.mappings.push(mapping);
            };

            $scope.mappings.sort(function(a,b) {
                if(a.key < b.key){
                    return -1;
                }
                else if (b.key > a.key) {
                    return 1;
                }
                return 0
            });

            // Convert joins into a list
            $scope.joins = $scope.model.joins || [];

            // Every controller should have `content` object set – this will
            // be used by reusable views
            $scope.contentType = "model";
            $scope.content = $scope.model;
            $scope.dims_by_id = {}

            for(i in $scope.dimensions){
                dim = $scope.dimensions[i]
                $scope.dims_by_id[dim.id] = dim
            };    

            $scope.$broadcast('modelLoaded');
        });

        $scope.modelObject = null;

        // Enumerations for selection lists
        // ================================
        //
        // For more information see Angular ng-select documentation.
        //

        $scope.functions = [
            {"name": "count", "label": "Record count"}, 
            {"name": "count_nonempty", "label": "Count of non-empty values"},
            {"name": "sum", "label": "Sum"},
            {"name": "min", "label": "Min"},
            {"name": "max", "label": "Max"},
            {"name": "avg", "label": "Average"},
            {"name": "stddev", "label": "Standard deviation"},
            {"name": "variance", "label": "Variance"},
            {"name": "sma", "label": "Simple moving average"},
            {"name": "wma", "label": "Weighted moving average"},
            {"name": null, "label": "Other/native..."},
        ];

        $scope.mappingTypes = [
            {"name": "string", "label": "String"},
            {"name": "sql", "label": "SQL"},
            {"name": "mongo", "label": "Mongo"},
            {"name": "json", "label": "JSON (text)"}
        ]

        $scope.providers = [
            {"name": "default", "label": "Default (static JSON)"},
            {"name": "mixpanel", "label": "Mixpanel"},
            {"name": "", "label": "Other..."}
        ]

        $scope.browsers = [
            {"name": "default", "label": "Default"},
            {"name": "mixpanel", "label": "Mixpanel"},
            {"name": "mongo2", "label": "MongoDB"},
            {"name": "slicer", "label": "Slicer Server"},
            {"name": "sql", "label": "SQL Star/Snowflake"},
            {"name": "", "label": "Other..."}
        ]

        $scope.cardinalities = [
            {"name": "", "label": "Default"}, 
            {"name": "tiny", "label": "Tiny (up to 5 members)"},
            {"name": "low", "label": "Low (5 to 50 members – in a list view)"},
            {"name": "medium", "label": "Medium (more than 50 – for a search field)"},
            {"name": "high", "label": "High (slicing required)"}
        ];

        $scope.dimensionRoles = [
            {"name": "", "label": "Default"}, 
            {"name": "time", "label": "Date/Time"}
        ];

        $scope.levelRoles = {
            time: [
                {"name": "", "label": "Default"}, 
                {"name": "year", "label": "Year"},
                {"name": "quarter", "label": "Quarter"},
                {"name": "month", "label": "Month"},
                {"name": "day", "label": "Day"},
                {"name": "hour", "label": "Hour"},
                {"name": "minute", "label": "Minute"}
            ]
        };

        $scope.joinMethods = [
            {"name": "", "label": "Default"}, 
            {"name": "match", "label": "Match (inner)"},
            {"name": "master", "label": "Master (left outer)"},
            {"name": "detail", "label": "Detail (right outer)"}
        ];

        $scope.storeTypes = [
            {"name": "mixpanel", "label": "Mixpanel"},
            {"name": "mongo", "label": "Mongo"},
            {"name": "slicer", "label": "Slicer"},
            {"name": "sql", "label": "SQL"}, 
            {"name": "", "label": "Other"}
        ];

        $scope.mappingEditors = [
            "sql", "mongo"
        ];

        PhysicalObject($scope);

        $scope.save = function() {
            // TODO: same code is in CubeController.save
            var mappings = {}

            for(var i in $scope.mappings) {
                mapping = $scope.mappings[i];
                if(mapping.type == "string"){
                    value = mapping.stringValue;
                }
                else {
                    value = mapping.value;
                }
                mappings[mapping.key] = value;
            }

            $scope.model.mappings = mappings;
            $scope.model.joins = $scope.joins;

            console.log("Saving model...");
            console.debug("scope: " + $scope.$id);
            $http.put("model", $scope.model);

            $scope.$broadcast("save");

        };
        $scope.reset = function() {
            console.log("Reseting the model, reload required.")
            $http.get("reset");
            $scope.$digest()
        };
    }
]);


ModelerControllers.controller('CubeListController', ['$scope', '$http', '$q',

    function ($scope, $http, $q) {
        $http.get('cubes').success(function(data) {
            $scope.cubes = data;
            // TODO: set content = cubes
        });
        
        $scope.idSequence = 1;

        $scope.addCube = function() {
            var new_cube = $http.put('new_cube');

            $q.all([new_cube]).then(function(results){
                var cube = results[0].data;

                $scope.cubes.push(cube);
            });
        };    
    }
]);

ModelerControllers.controller('DimensionListController', ['$scope', '$http', '$q',

    function ($scope, $http, $q) {
        $http.get('dimensions').success(function(data) {
            $scope.dimensions = data;
            // TODO: set content = dimensions
        });
        
        $scope.idSequence = 1;

        $scope.addDimension = function() {
            var new_dimension = $http.put('new_dimension');

            $q.all([new_dimension]).then(function(results){
                var dim = results[0].data;

                $scope.dimensions.push(cube);
            });
        };    

    }
]);

ModelerControllers.controller('CubeController', ['$scope', '$routeParams', '$http',
    function ($scope, $routeParams, $http) {
        id = $routeParams.cubeId

        $http.get('cube/' + id).success(function(cube) {
            $scope.cube = cube;
            $scope.content = cube

            $scope.cube_dimensions = []
            names = cube.dimensions || []
            for(var i in names) {
                var name = names[i]
                var dim = _.find($scope.dimensions,
                                 function(d) {return d.name == name});

                if (dim) {
                    $scope.cube_dimensions.push(dim);
                }
                else {
                    dim = { name: name, label: name + " (unknown)"}
                    $scope.cube_dimensions.push(dim)
                }   
            };

            $scope.available_dimensions = _.filter($scope.dimensions, function(d) {
                return names.indexOf(d.name) === -1;
            });

            var mappings = cube.mappings

            if(!mappings){
                mappings = {}
            };

            // Convert mappings into a list
            var mapping_list = [];

            for(var key in mappings) {
                value = mappings[key];
                mapping = {
                    "key": key,
                    "value": mappings[key]
                };
                if(_.isString(value)) {
                    mapping["string"] = value;
                    mapping["type"] = "string";
                };
                mapping["jsonString"] = JSON.stringify(value, null, "    ");
                mapping_list.push(mapping);


                // Assign the mapping to an attribute
                attr = CM.cube_attribute(cube, key);
                if(attr) {
                    attr.mapping = mapping;
                };
            };

            $scope.mappings = mapping_list;
            //
            // Convert joins into a list

            // Convert joins into a list
            $scope.joins = cube.joins || [];

            $scope.$broadcast('cubeLoaded');
        });

        $scope.active_tab = $routeParams.activeTab || "info";
        $scope.cubeId = id;

        $scope.includeDimension = function(dim_id) {
            var dim = $scope.dims_by_id[dim_id];
             
            // We just need dimension name
            $scope.cube.dimensions.push(dim.name);
            
            // This is for Angular view refresh
            $scope.cube_dimensions.push(dim);
            index = $scope.available_dimensions.indexOf(dim);
            if(index != -1){
                $scope.available_dimensions.splice(index, 1)
            };
        };   
        $scope.removeDimension = function(dim_id) {
            var dim = $scope.dims_by_id[dim_id];
             
            // We just need dimension name
            index = $scope.cube.dimensions.indexOf(dim.name);
            if(index != -1){
                $scope.cube.dimensions.splice(index, 1)
                $scope.cube_dimensions.splice(index, 1);
            };
            
            // This is for Angular view refresh
            // ???
            $scope.available_dimensions = _.filter($scope.dimensions, function(d) {
                return $scope.cube.dimensions.indexOf(d.name) === -1;
            });
        };

        PhysicalObject($scope);

        $scope.save = function(){
            // FIXME: Same code is in the model controller
            var mappings = {}
            var maplist = []
            var cube;

            cube = angular.copy($scope.cube)

            maplist = maplist.concat($scope.mappings);
            maplist = maplist.concat(CM.collect_attribute_mappings(cube.aggregates));
            maplist = maplist.concat(CM.collect_attribute_mappings(cube.measures));
            maplist = maplist.concat(CM.collect_attribute_mappings(cube.details));

            for(var i in maplist) {
                mapping = maplist[i];
                if(mapping.type == "string"){
                    value = mapping.stringValue;
                }
                else {
                    value = mapping.value;
                }
                mappings[mapping.key] = value;
            }


            $scope.cube.mappings = mappings;
            console.log("Saving cube " + $scope.cubeId);
            $http.put("cube/" + $scope.cubeId, $scope.cube);
        };

        $scope.$on("save", $scope.save);

    }
]);


function AttributeListController(type, label){
    return function($scope, modelObject) {
        $scope.attributeType = type;
        $scope.attributeLabel = label;

        $scope.loadAttributes = function() {
            type = $scope.attributeType;
            if(type == "measure"){
                $scope.attributes = $scope.cube.measures;
            }
            else if(type == "aggregate"){
                $scope.attributes = $scope.cube.aggregates;
            }
            else if(type == "detail"){
                $scope.attributes = $scope.cube.details;
            }
            else if(type == "level_attribute"){
                $scope.attributes = $scope.level.attributes;
            };

            // Set attribute selection, if there are any attributes
            if($scope.attributes.length >= 1){
                $scope.content = $scope.attributes[0];
            }
            else {
                $scope.content = null;
            };       
        };   

        if($scope.cube) {
            $scope.loadAttributes();
        }

        $scope.$on('cubeLoaded', $scope.loadAttributes);

        $scope.selectAttribute = function(attribute) {
            $scope.content = attribute;
            if(!attribute.mapping){
                attribute.mapping = {"key": attribute.name};
            };
        };

        $scope.removeAttribute = function(index) {
            $scope.attributes.splice(index, 1);
        }; 

        $scope.addAttribute = function() {
            attribute = {"name": "new_"+type}
            attribute.mapping = {};
            $scope.content = attribute;
            $scope.attributes.push(attribute);
        };
    };      
};

ModelerControllers.controller('CubeMeasureListController', ['$scope',
                              AttributeListController("measure", "Measure")]);

ModelerControllers.controller('CubeAggregateListController', ['$scope',
                              AttributeListController("aggregate", "Aggregate")]);

ModelerControllers.controller('CubeDetailListController', ['$scope',
                              AttributeListController("detail", "Detail")]);

ModelerControllers.controller('DimensionController', ['$scope', '$routeParams', '$http',
    function ($scope, $routeParams, $http) {
        id = $routeParams.dimId

        $http.get('dimension/' + id).success(function(dim) {
            $scope.dimension = dim;
            $scope.content = dim;

            // We are expected to get "fixed" dimensions from the server
            // For more information see fix_dimension_metadata() in
            // cubes.model module
            var levels = {}
            for(var i in dim.levels){
                level = dim.levels[i];
                levels[level.name] = level
            }
            // Resolve relationships
            var hierarchies = dim.hierarchies;
            if(!hierarchies || hierarchies.length == 0){
                hierarchies = [];
                dim.hierarchies = hierarchies;
            }

            // Remap level names to levels
            for(var i in hierarchies){
                hier = hierarchies[i];
                hier.levels = _.map(hier.levels, function(l) {
                    return levels[l];
                })
            }

            if(dim.default_hierarchy_name) {
                $scope.defaultHierarchy = _.find($scope.dimension.hierarchies, function(h) {
                    return (h.name == dim.default_hierarchy_name);
                });
            }
            else {
                $scope.defaultHierarchy = null;
            };

            var attrs = CM.dimension_attributes(dim);
            var simplify = (attrs.length == 1)

            for(var i in attrs){
                attr = attrs[i];
                if(simplify) {
                    key = dim.name;
                }
                else {
                    key = dim.name + "." + attr.name;
                }
                value = $scope.model.mappings[key];
                mapping = {};
                mapping.value = value || {};
                attr.mapping = mapping;
            }

            $scope.$broadcast('dimensionLoaded');
        });

        $scope.active_tab = $routeParams.activeTab || "info";
        $scope.dimId = id;

        // Save!
        // =====
        $scope.save = function(){
            // Remove relationships

            var dim = angular.copy($scope.dimension);

            for(var i in dim.levels) {
                level = dim.levels[i];
                if(level.key) {
                    level.key = level.key.name;
                };
                if(level.labelAttribute) {
                    level.labelAttribute = level.labelAttribute.name;
                };
            };

            var attrs = CM.dimension_attributes(dim);
            var simplify = (attrs.length == 1);
            var mappings;

            mappings = CM.collect_attribute_mappings(attrs,
                                                     dim.name,
                                                     simplify);
            for(m in mappings) {
                mapping = mappings[m];
                $scope.model.mappings[mapping.key] = mapping.value;
            };
            // TODO: save the model as well, if mappings have changed

            for(var h in dim.hierarchies) {
                hier = dim.hierarchies[h];
                names = _.map(hier.levels, function(level) { return level.name; })
                hier.levels = names;
            };

            console.log("Saving dimension " + $scope.dimId)
            $http.put("dimension/" + $scope.dimId, dim);
        };

        $scope.$on('save', $scope.save);
    }
]);

ModelerControllers.controller('HierarchiesController', ['$scope',
    function ($scope) {
        $scope.content = null;

        $scope.$on('dimensionLoaded', function() {
            if(hierarchies.length > 0){
                $scope.selectHierarchy(hierarchies[0]);
            }
            else {
                $scope.selectHierarchy(null);
            }
        });

        $scope.selectHierarchy = function(hier) {
            $scope.contentType = "hierarchy";
            $scope.content = hier;
            $scope.hierarchy = hier

            if(hier) {
                $scope.availableLevels = _.filter($scope.dimension.levels, function(l) {
                    return (hier.levels.indexOf(l) === -1);
                });
                $scope.isAnyHierarchy = false;
            }
            else
            {
                $scope.availableLevels = $scope.dimension.levels;                
                $scope.isAnyHierarchy = true;
            }
        };

        $scope.addHierarchy = function() {
            hierarchies = $scope.dimension.hierarchies;
            hier = {
                name: "new_hierarchy",
                label: "New Hierarchy",
                levels: []
            };
            hierarchies.push(hier);

            $scope.selectHierarchy(hier);
        }

        $scope.removeHierarchy = function(hier){
            hierarchies = $scope.dimension.hierarchies;
            index = hierarchies.indexOf(hier);
            hierarchies.splice(index, 1);
            if($scope.hierarchies.length > 0){
                $scope.selectHierarchy(hierarchies[0]);
            }
            else {
                $scope.selectHierarchy(null)
            }
        };

        $scope.setDefaultHierarchy = function(hier) {
            if($scope.defaultHierarchy != hier) {
                $scope.defaultHierarchy = hier;
                $scope.dimension.default_hierarchy_name = hier.name;
            }
            else {
                $scope.defaultHierarchy = null;
                $scope.dimension.default_hierarchy_name = null;
            };
        };

        // Levels
        // ======

        $scope.includeLevel = function(level){
            hier = $scope.hierarchy;

            if(! hier.levels) {
                hier.levels = [];
            };

            // TODO: use level object, this will be broken when level is
            // renamed
            hier.levels.push(level);

            $scope.selectHierarchy(hier);
        };

        $scope.moveLevel = function(offset, level){
            _.relativeMoveItem($scope.hierarchy.levels, level, offset);
        };

        $scope.excludeLevel = function(level){
            hier = $scope.hierarchy;
            index = hier.levels.indexOf(level);
            hier.levels.splice(index, 1);

            $scope.selectHierarchy(hier); 
        };

        $scope.selectLevel = function(level) {
            $scope.contentType = "level";
            $scope.content = level;
            $scope.attributes = level.attributes;
            $scope.level = level;

            if(level){
                if(level.label_attribute) {
                    $scope.labelAttribute = _.find($scope.attributes,
                                                   function(attr){
                                                       return attr.name == level.label_attribute;
                                                   })
                }
                else {
                    $scope.labelAttribute = null;
                }
                if(level.key) {
                    $scope.key = _.find($scope.attributes,
                                        function(attr){
                                            return attr.name == level.key;
                                        })
                }
                else {
                    $scope.key = null;
                }
            };       
        };

        $scope.addLevel = function() {
            obj = {
                name: "new_level",
                label: "New Level",
                attributes: [{"name": "new_attribute"}]
            };
            $scope.dimension.levels.push(obj);

            if(!$scope.isAnyHierarchy) {
                $scope.hierarchy.levels.push(obj)
            }

            $scope.selectLevel(obj);
        };

        // Attributes
        // ==========

        $scope.selectAttribute = function(attribute) {
            $scope.contentType = "attribute";
            $scope.content = attribute;
            attribute.mapping = attribute.mapping || {};
        };

        $scope.moveAttribute = function(offset, attr){
            _.relativeMoveItem($scope.attributes, attr, offset);
        };

        $scope.addAttribute = function() {
            attr = {
                name: "new_attribute",
                label: "New Attribute",
                mapping: { value: {} }
            };
            $scope.attributes.push(attr);

            $scope.selectAttribute(attr);
        };

        $scope.removeAttribute = function(attr){
            index = $scope.attributes.indexOf(attr);
            $scope.attributes.splice(index, 1);
            if($scope.attributes > 0){
                $scope.selectAttribute($scope.attributes[0]);
            }
            else {
                $scope.selectAttribute(null)
            }
        };

        $scope.setKeyAttribute = function(attr) {
            if($scope.key != attr) {
                $scope.key = attr;
                $scope.level.key = attr.name;
            }
            else {
                $scope.key = null;
                $scope.level.key = null;
            }
        };

        $scope.setLabelAttribute = function(attr) {
            if($scope.labelAttribute != attr) {
                $scope.labelAttribute = attr;
                $scope.level.label_attribute = attr.name;
            }
            else {
                $scope.labelAttribute = null;
                $scope.level.label_attribute = null;  
            };
        };

        // Tri-state flag: asc/desc/none
        $scope.setOrderAttribute = function(attr) {
            if($scope.orderAttribute != attr) {
                $scope.orderAttribute = attr;
                $scope.level.order_attribute = attr.name;
                $scope.level.order = "asc";
            }
            else {
                order = $scope.level.order;
                if($scope.level.order == "asc"){
                    $scope.level.order = "desc";
                }
                else{
                    $scope.orderAttribute = null;
                    $scope.level.order_attribute = null;
                    $scope.level.order = null;
                }
            };
        };

    }
]);


ModelerControllers.controller('MappingListController', ['$rootScope', '$scope',
    function ($rootScope, $scope) {
        // Note: We are operating on parent's mappings, but we preserve our
        // scope content

        $scope.reload = function() {
            if($scope.mappings && $scope.mappings.lenghth > 0) {
                $scope.content = $scope.mappings[0];
            }
            else {
                $scope.content = null;
            }
        };

        $scope.$on("modelLoaded", $scope.reload);
        $scope.$on("cubeLoaded", $scope.reload);

        $scope.selectMapping = function(mapping) {
            // TODO: somehow this does not select the edit list
            $scope.contentType = "mapping";
            $scope.content = mapping;
            $scope.jsonIsValid = true;
            console.log("Selected type (from root): " + $rootScope.storeType)
        };

        $scope.mappingTypeChanged = function(selection) {
            if($scope.content && $scope.contentType == "mapping") {
                // TODO: add JSON string validation
                if(selection == "jsonstr") {
                    $scope.content.jsonString = JSON.stringify($scope.content.value, null, "    ");
                    $scope.jsonIsValid = true;
                }
                else if($scope.content.type == "jsonstr") {
                    $scope.content.value = JSON.parse($scope.content.jsonString);
                }
                $scope.content.type = selection;
            }
        };

        $scope.addMapping = function() {
            mapping = {
                key: "unnamed"
            };

            $scope.mappings.push(mapping);
            $scope.selectMapping(mapping);
        };

        $scope.removeMapping = function(obj) {
            var last = _.removeListItem($scope.mappings, obj);
            if(obj === $scope.content) {
                $scope.selectMapping(last);
            }
        };

    }
]);

ModelerControllers.controller('JoinListController', ['$scope',
    function ($scope) {
        $scope.selectJoin = function(join) {
            // TODO: somehow this does not select the edit list
            $scope.contentType = "join";
            $scope.content = join;
        };

        $scope.addJoin = function() {
            join = {
                master: {},
                detail: {}
            };

            $scope.joins.push(join);
            $scope.selectJoin(join);
        };

        $scope.removeJoin = function(join) {
            var last = _.removeListItem($scope.joins, join);
            if(join === $scope.content) {
                $scope.selectJoin(last);
            }
        };

        $scope.moveJoin = function(offset, join){
            _.relativeMoveItem($scope.joins, join, offset);
        };

        if($scope.joins && $scope.joins.length > 0){
            $scope.selectJoin($scope.joins[0]);
        };

    }
]);


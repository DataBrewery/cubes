import cubes.common
import cubes.browser
import base

import itertools
import logging

try:
    import pymongo
    import bson
except ImportError:
    pass

class MongoSimpleCubeBuilder(object):
    """Construct preaggregated cube.
    """
    def __init__(self, cube, database, 
                    fact_collection, 
                    cube_collection = None,
                    measures = None,
                    aggregate_flag_field = "_is_aggregate",
                    required_dimensions = ["date"]):
        """Creates simple cube builder in mongo. See :meth:`MongoSimpleCubeBuilder.compute` for more 
        information about computation algorithm
        
        :Attributes:
            * `cube` - description of a cube from logical model
            * `fact_collection` - either name or mongo collection containing facts (should correspond)
              to `cube` definition
            * `cube_collection` - name or mongo collection where computed cell aggregates will be
              stored. By default it is the same collection as fact collection. Make sure to properely
              set `aggregate_flag_field`.
            * `measures` - list of attributes that are going to be aggregated. By default it is
              ``[amount]``
            * `aggregate_flag_field` - name of field (key) that distincts fact fields from aggregated
              records. Should be used when fact collection and cube collection is the same. By default
              it is ``_is_aggregate``.
            * `required_dimensions` - dimensions that are required for all cells. By default: 
              ``[date]``
        """
                    
        self.cube = cube
        self.database = database
        self.aggregate_flag_field = aggregate_flag_field

        self.fact_collection = fact_collection
        if cube_collection:
            self.cube_collection = cube_collection
        else:
            self.cube_collection = fact_collection
            
        if type(self.fact_collection) == str:
            self.fact_collection = self.database[self.fact_collection]

        if type(self.cube_collection) == str:
            self.cube_collection = self.database[self.cube_collection]
            
        if required_dimensions:
            dims = []
            for dim in required_dimensions:
                dims.append(self.cube.dimension(dim))

        self.required_dimensions = dims
        self.measure_agg = None
        self.selectors = None
        
        if measures == None:
            measures = ["amount"]
            
        self.measures = measures
        
        self.log = logging.getLogger(cubes.logger_name)
        
        self.cell_record_name = "_selector"
        self.cell_reference_record_name = "_cell"
        
    def compute(self):
        """Compute a multidimensional cube. Computed aggregations for cells can be stored either
        in separate collection or in the same source - fact collection. Attribute `aggregate_flag_field`
        is used to distinct between facts and aggregated cells.
        
        Algorithm:
        
        #. Compute all dimension combinations (for all levels if there are any hierarchies). Each
           combination is called `selector` and is represented by a list of tuples: (dimension, levels).
           For more information see: :meth:`cubes.common.compute_dimension_cell_selectors`.

        #. Compute aggregations for each point within dimension selector. Use MongoDB group function
           (alternative to map-reduce).
        
        #. Each record for aggregated cell is stored in target collection (see above).

        This is naive non-optimized method of cube computation: no aggregations are reused for
        computation.
        """

        self.log.info("Computing cube %s" % self.cube.name)

        self.cube_collection.remove({self.aggregate_flag_field: True})

        selectors = cubes.common.compute_dimension_cell_selectors(self.cube.dimensions,
                                                           self.required_dimensions)

        self.log.info("got %d dimension level selectors ", len(selectors))

        for selector in selectors:
            self.compute_cell(selector)

        self.cube_collection.ensure_index(self.cell_record_name)
                                                                
    def compute_cell(self, selector):
        """ 
        Compute aggregation for cell specified by selector. cell is computed using MongoDB
        aggregate_ function. Computed records are inserted into `cube_collection` and they contain:
        
        * key fields used for grouping
        * aggregated measures suffixed with `_sum`, for example: `amount_sum`
        * record count in `record_count`
        * cell selector as `_selector` (configurable) with dimension names as keys and current
          dimension levels as values, for example: {"date": ["year", "month"] }
        * cell reference as `_cell` (configurable) with dimension names as keys and level 
          keys forming dimension paths as values, for example: {"date": [2010, 10] }

        .. _aggregate: http://www.mongodb.org/display/DOCS/Aggregation#Aggregation-Group

        :Arguments:
            * `selector` is a list of tuples: (dimension, level_names)
                    
        .. note::
        
            Only 'sum' aggregation is being computed. Other aggregations might be implemented in the
            future, such as average, min, max, rank, ...
        """
        self.log.info("computing selector")

        key_maps = []
        attrib_maps = []
        selector_record = {}
        
        for dimsel in selector:
            dim = dimsel[0]
            levels = dimsel[1]
            self.log.info("-- dimension: %s levels: %s", dim.name, levels)

            level_names = []
            for level in levels:
                level_names.append(level.name)
                mapped = base.dimension_field_mapping(self.cube, dim, level.key)
                key_maps.append(mapped)
                
                for field in level.attributes:
                    mapped = base.dimension_field_mapping(self.cube, dim, field)
                    attrib_maps.append((mapped[0], field))

            selector_record[dim.name] = level_names
            

        ###########################################
        # Prepare group command parameters
        #
        # condition - filter condition for find() (check for existence of keys)
        # keys - list of keys to be used for grouping
        # measures - list of measures

        condition = {}
        keys = []
        for mapping in key_maps:
            mapped_key = mapping[0]
            condition[mapped_key] = { "$exists" : True}
            keys.append(mapped_key)

        fields = []
        for mapping in attrib_maps:
            mapped = mapping[0]
            fields.append(mapped)
        
        for measure in self.measures:
            mapping = base.fact_field_mapping(self.cube, measure)
            fields.append(mapping[0])
            
        self.log.info("condition: %s", condition)
        self.log.info("keys: %s", keys)
        self.log.info("fields: %s", fields)

        # Exclude aggregates:
        condition[self.aggregate_flag_field] = {'$ne': True}

        ####################################################
        # Prepare group functions + reduce + finalize
        #

        initial = { "record_count": 0 }

        aggregate_lines = []
        for measure in self.measures:
            measure_agg_name = measure + "_sum"
            line = "out.%s += doc.%s;" % (measure_agg_name, measure)
            aggregate_lines.append(line)
            initial[measure_agg_name] = 0

        reduce_function = '''
        function(doc, out) {
                out.record_count ++;
                %(aggregate_lines)s
        }\n''' % {"aggregate_lines": "\n".join(aggregate_lines)}

        finalize_function = None

        cursor = self.fact_collection.group(key = keys, condition = condition,
                                            initial = initial, reduce = reduce_function,
                                            finalize = finalize_function)

        for record in cursor:
            # use: cubes.commons.expand_dictionary(record)
            cell = {}
            for dimsel in selector:
                dimension, levels = dimsel
                path = []
                for level in levels:
                    mapped = base.dimension_field_mapping(self.cube, dimension, level.key)
                    path.append(record[mapped[0]])
                cell[dimension.name] = path

            record = self.construct_record(record)
            record[self.aggregate_flag_field] = True
            record[self.cell_record_name] = selector_record
            record[self.cell_reference_record_name] = cell
            self.cube_collection.insert(record)

    def construct_record(self, record):
        result = {}
        for key, value in record.items():
            current = result
            path = key.split(".")
            for part in path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[path[-1]] = value
        return result
      

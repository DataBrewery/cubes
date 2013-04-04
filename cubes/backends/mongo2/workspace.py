import logging
from cubes.mapper import SnowflakeMapper, DenormalizedMapper, coalesce_physical
from cubes.common import get_logger
from cubes.errors import *
from cubes.browser import *
from cubes.computation import *
from cubes.workspace import Workspace

import collections
import copy
import pymongo
import bson


__all__ = [
    "create_workspace"
]


def create_workspace(model, **options):
    return MongoWorkspace(model, **options)


class MongoWorkspace(Workspace):

    def __init__(self, model, **options):
        super(MongoWorkspace, self).__init__(model)
        self.logger = get_logger()
        self.options = options
        self.metadata = {}

    def browser(self, cube, locale=None):
        print 'browser:', cube, locale

        model = self.localized_model(locale)
        cube = model.cube(cube)

        browser = MongoBrowser(
            cube,
            locale=locale,
            metadata=self.metadata,
            **self.options)

        return browser


class MongoBrowser(AggregationBrowser):
    def __init__(self, cube, locale=None, metadata={}, **options):
        super(MongoBrowser, self).__init__(cube)

        mongo_client = pymongo.MongoClient(options.get('url'))
        mongo_client.read_preference = pymongo.read_preferences.ReadPreference.SECONDARY

        db, coll = options.get('database'), options.get('collection')

        self.data_store = mongo_client[db][coll]

        self.mapper = SnowflakeMapper(cube, locale)

    def aggregate(self, cell=None, measures=None, drilldown=None, 
                  attributes=None, order=None, page=None, page_size=None, 
                  **options):
        cell = cell or Cell(self.cube)

        if measures:
            measures = [self.cube.measure(measure) for measure in measures]

        result = AggregationResult(cell=cell, measures=measures)

        drilldown_levels = None

        if drilldown:
            drilldown_levels = levels_from_drilldown(cell, drilldown)
            dim_levels = {}
            for dim, hier, levels in drilldown_levels:
                dim_levels["%s@%s" % (dim, dim.hierarchy(hier))] = [str(level) for level in levels]
            result.levels = dim_levels

        summary, cursor = self._do_aggregation_query(cell=cell, measures=measures, attributes=attributes, drilldown=drilldown_levels, order=order, page=page, page_size=page_size)
        result.cells = cursor
        result.summary = summary

        return result


    def facts(self, cell=None, order=None, page=None, page_size=None, **options):
        raise NotImplementedError

    def fact(self, key):
        raise NotImplementedError

    def values(self, cell, dimension, depth=None, paths=None, hierarchy=None, order=None, page=None, page_size=None, **options):
        raise NotImplementedError

    def _do_aggregation_query(self, cell, measures, attributes, drilldown, order, page, page_size):

        # determine query for cell cut
        find_clauses = []
        query_obj = {}
        if self.cube.mappings and self.cube.mappings.get('__query__'):
            query_obj.update(copy.deepcopy(self.cube.mappings['__query__']))

        find_clauses = reduce(lambda i, c: i + c, [self._query_conditions_for_cut(cut) for cut in cell.cuts], [])

        if find_clauses:
            query_obj.update({ "$and": find_clauses })
        
        fields_obj = {}
        if attributes:
            for attribute in attributes:
                fields_obj[ self.mapper.physical(attribute) ] = 1

        # if no drilldown, no aggregation pipeline needed.
        if not drilldown:
            return (self.data_store.find(query_obj).count(), [])

        # drilldown, fire up the pipeline
        group_obj = {}
        group_id = {}
        for dim, hier, levels in drilldown:
            for level in levels:
                phys = self.mapper.physical(level.key).column
                fields_obj[phys] = 1
                group_id[level.key.ref()] = "$%s" % phys

        group_obj = { "_id": group_id, "record_count": { "$sum": 1 } }

        pipeline = [
            { "$match": query_obj },
            { "$project": fields_obj },
            { "$group": group_obj }
        ]

        if order:
            pipeline.append({ "$sort": self._order_to_sort_object(order) })
        
        if page and page > 0:
            pipeline.append({ "$skip": page * page_size })
        
        if page_size and page_size > 0:
            pipeline.append({ "$limit": page_size })
        
        result_items = []
        for item in self.data_store.aggregate(pipeline).get('result', []):
            new_item = {}
            new_item.update(item['_id'])
            new_item['record_count'] = item['record_count']
            result_items.append(new_item)
        return (None, result_items)

    def _query_conditions_for_cut(self, cut):
        conds = []
        cut_dimension = self.cube.dimension(cut.dimension)
        cut_hierarchy = cut_dimension.hierarchy(cut.hierarchy)
        if isinstance(cut, PointCut):
            # one condition per path element
            for idx, p in enumerate(cut.path):
                conds.append( self._query_condition_for_path_value(cut_hierarchy.levels[idx].key, p, "$ne" if cut.invert else None) )
        elif isinstance(cut, SetCut):
            for path in cut.paths:
                path_conds = []
                for idx, p in enumerate(path):
                    path_conds.append( self._query_condition_for_path_value(cut_hierarchy.levels[idx].key, p, "$ne" if cut.invert else None) )
                conds.append({ "$and" : path_conds })
            conds = [{ "$or" : conds }]
        # FIXME for multi-level range: it's { $or: [ level_above_me < value_above_me, $and: [level_above_me = value_above_me, my_level < my_value] }
        # of the level value.
        elif isinstance(cut, RangeCut):
            if cut.from_path:
                last_idx = len(cut.from_path) - 1
                for idx, p in enumerate(cut.from_path):
                    op = ( ("$lt", "$ne") if cut.invert else ("$gte", None) )[0 if idx == last_idx else 1]
                    conds.append( self._query_condition_for_path_value(cut.dimension, p, op))
            if cut.to_path:
                last_idx = len(cut.to_path) - 1
                for idx, p in enumerate(cut.to_path):
                    op = ( ("$gt", "$ne") if cut.invert else ("$lte", None) )[0 if idx == last_idx else 1]
                    conds.append( self._query_condition_for_path_value(cut.dimension, p, "$gt" if cut.invert else "$lte") )
        else:
            raise ValueError("Unrecognized cut object: %r" % cut)
        return conds

    def _query_condition_for_path_value(self, attr, value, op=None):
        tcr = self.mapper.physical(attr)
        if op is None:
            return { tcr.column : value }
        else:
            return { tcr.column : { op : value } }

    def _order_to_sort_object(self, order=None):
        if not order:
            return []

        order_by = collections.OrderedDict()
        # each item is a 2-tuple of (logical_attribute_name, sort_order_string)
        for attrname, sort_order_string in order:
            sort_order = -1 if sort_order_string in ('desc', 'DESC') else 1
            attribute = self.mapper.attribute(attrname)
            field = self.mapper.physical(attribute)

            if attrname not in order_by:
                order_by[attrname] = ( attribute.ref(), sort_order )
        return dict( order_by.values() )


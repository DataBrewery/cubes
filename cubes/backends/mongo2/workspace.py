import logging
from cubes.mapper import SnowflakeMapper, DenormalizedMapper
from cubes.common import get_logger
from cubes.errors import *
from cubes.browser import *
from cubes.computation import *
from cubes.workspace import Workspace

import pymongo
from pymongo.son import SON
import bson


__all__ = [
    "create_workspace"
]

def create_workspace(model, **options):
    print 'MODEL:', model
    print 'options:', options

    return MongoWorkspace(model, options)



class MongoWorkspace(Workspace):
    def __init__(self, model, **options):
        super(MongoWorkspace, self).__init__(model)
        self.data_store = data_store
        self.logger = get_logger()

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


def get_mongo_collection(**options):
    mongo_client = pymongo.MongoClient(**options)
    return mongo_client[ options.get('database') ][ options.get('collection') ]

class MongoBrowser(AggregationBrowser):
    def __init__(self, cube, locale=None, metadata={}, **options):
        super(MongoBrowser, self).__init__(cube)
        self.data_store = get_mongo_collection(**options)

    def aggregate(self, cell=None, measures=None, drilldown=None, 
                  attributes=None, order=None, page=None, page_size=None, 
                  **options):
        if not cell:
            cell = Cell(self.cube)

        if measures:
            measures = [self.cube.measure(measure) for measure in measures]

        result = AggregationResult(cell=cell, measures=measures)

        drilldown_levels = None

        if drilldown:
            drilldown_levels = levels_from_drilldown(cell, drilldown)
            dim_levels = {}
            for dim, levels in drilldown_levels:
                dim_levels[str(dim)] = [str(level) for level in levels]
            result.levels = dim_levels

        cursor = self._do_aggregation_query(cell=cell, measures=measures, attributes=attributes, drilldown=drilldown_levels)
            result.cells = cursor

        return result


    def facts(self, cell=None, order=None, page=None, page_size=None, **options):
        raise NotImplementedError

    def fact(self, key):
        raise NotImplementedError

    def values(self, cell, dimension, depth=None, paths=None, hierarchy=None, order=None, page=None, page_size=None, **options):
        raise NotImplementedError

    def _do_aggregation_query(cell, measures, attributes, drilldown):
        query_obj = {}
        for cut in cell.cuts:
            query_obj.update(self._query_condition_for_cut(cut))
        fields_obj = {}
        if attributes:
            for attribute in attributes:
                fields_obj[ attribute.ref() ] = 1

        # if no drilldown, no aggregation pipeline needed.
        if not drilldown:
            return self.data_store.find(query_object).count()

        # drilldown, fire up the pipeline
        group_obj = {}
        group_id = {}
        for dim, levels in drilldown:
            for level in levels:
                # TODO probably need to map to physical here
                fields_obj[level.ref()] = 1
                group_id[level.ref()] = "$%s" % level.ref()

        group_obj = { "_id": group_id, "count": { "$sum": 1 } }

        pipeline = [
            { "$match": query_obj },
            { "$project": fields_obj },
            { "$group": group_obj }
            ]
        if order:
            pipeline.append({ "$sort": SON(self._order_to_sort_list(order)) })
        if page is not None and page_size is not None:
            if page > 0:
                pipeline.append({ "$skip": page * page_size })
            if page_size > 0:
                pipeline.append({ "$limit": page_size })
        return self.data_store.aggregate(pipeline).get('result', [])

    def _query_condition_for_cut(self, cut):
        # TODO 
        return {}

    def _order_to_sort_list(self, order=None):
        if not order:
            return []

        order_by = collections.OrderedDict()
        for item in order:
            sort_order = 1
            if isinstance(item, basestring):
                attribute = self.mapper.attribute(item)
                field = self._document_field(attribute)

            else:
                # item is a two-element tuple where first element is attribute
                # name and second element is ordering
                attribute = self.mapper.attribute(item[0])
                field = self._document_field(attribute)

            if item not in order_by:
                order_by[item] = (field, sort_order)
        return order_by.values()        

    def _document_field(self, ref):
        return str(ref)

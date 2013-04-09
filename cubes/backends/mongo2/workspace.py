import logging
from cubes.common import get_logger
from cubes.errors import *
from cubes.browser import *
from cubes.computation import *
from cubes.workspace import Workspace
from .mapper import MongoCollectionMapper

import collections
import copy
import pymongo
import bson

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from itertools import groupby
from functools import partial
import pytz

tz = pytz.timezone('America/New_York')
tz_utc = pytz.timezone('UTC')

__all__ = [
    "create_workspace"
]


def _calc_week(dt):
    year = dt.year

    dt = _get_next_weekdate(dt)

    count = 0
    while dt.year == year:
        count += 1
        dt -= timedelta(days=7)

    return count

def _get_next_weekdate(dt):
    dt = dt.replace(**{
            'hour': 0,
            'minute': 0,
            'second': 0,
            'microsecond': 0,
        })

    while dt.weekday() != 4:
        dt += timedelta(1)

    return dt

_datepart_functions = {
    'year': lambda x:x.year,
    'month': lambda x:x.month,
    'week': _calc_week,
    'day': lambda x:x.day,
    'hour': lambda x:x.hour,
}

_date_norm_map = {
    'month': 1,
    'day': 1,
    'hour': 0,
    'minute': 0, 
}


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

        self.mapper = MongoCollectionMapper(cube, locale)

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
        result.summary = { "record_count": summary }

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
                fields_obj[ escape_level(attribute.ref()) ] = self.mapper.physical(attribute).project_expression()

        # if no drilldown, no aggregation pipeline needed.
        if not drilldown:
            return (self.data_store.find(query_obj).count(), [])

        # drilldown, fire up the pipeline
        group_obj = {}
        group_id = {}

        date_processing = False
        date_transform = lambda x:x

        for dim, hier, levels in drilldown:

            # Special Mongo Date Hack for TZ Support
            if dim and dim.name.lower() == 'date':
                date_processing = True
                phys = self.mapper.physical(levels[0].key)
                date_idx = phys.project_expression()

                # add to $match and $project expressions
                query_obj.update(phys.match_expression(1, op='$exists'))
                fields_obj[date_idx[1:]] = 1

                group_id.update({
                    'year': {'$year': date_idx},
                    'month': {'$month': date_idx},
                    'day': {'$dayOfMonth': date_idx},
                    'hour': {'$hour': date_idx},
                })

                def _date_transform(item, date_field):
                    date_dict = {}
                    for k in ['year', 'month', 'day', 'hour']:
                        date_dict[k] = item['_id'].pop(k)
                    date_dict.update({'tzinfo': tz_utc})

                    date = datetime(**date_dict)
                    date = date.astimezone(tz=tz) # convert to eastern

                    item['_id'][date_field] = date
                    return item

                date_transform = partial(_date_transform, date_field=dim.name)

            else:
                for level in levels:
                    phys = self.mapper.physical(level.key)
                    exp = phys.project_expression()
                    fields_obj[escape_level(level.key.ref())] = exp
                    group_id[escape_level(level.key.ref())] = "$%s" % escape_level(level.key.ref())
                    query_obj.update(phys.match_expression(1, op='$exists'))

        agg = self.cube.measure('record_count').aggregations[0]
        if agg == 'count':
            agg = 'sum'
            agg_field = 1
        else:
            agg_field = self.cube.mappings.get('record_count')
            if agg_field:
                fields_obj[ agg_field ] = 1
            agg_field = "$%s" % agg_field if agg_field else 1
        group_obj = { "_id": group_id, "record_count": { "$%s" % agg: agg_field } }

        pipeline = []
        pipeline.append({ "$match": query_obj })
        if fields_obj:
            pipeline.append({ "$project": fields_obj })
        pipeline.append({ "$group": group_obj })

        if not date_processing and order:
            pipeline.append({ "$sort": self._order_to_sort_object(order) })
        
        if not date_processing and page and page > 0:
            pipeline.append({ "$skip": page * page_size })
        
        if not date_processing and page_size and page_size > 0:
            pipeline.append({ "$limit": page_size })
        
        result_items = []
        print "PIPELINE", pipeline

        results = self.data_store.aggregate(pipeline).get('result', [])
        results = [date_transform(r) for r in results]

        if date_processing:
            dategrouping = ['year', 'month', 'week', 'day', 'hour',]
            datenormalize = ['year', 'month', 'day', 'hour',]

            # calculate correct date:level
            for dim, hier, levels in drilldown:
                if dim and dim.name.lower() == 'date':
                    dategrouping = [str(l).lower() for l in levels]
                    for dg in dategrouping:
                        datenormalize.remove(dg)
                    break

            def _date_key(item, dategrouping=['year', 'month', 'week', 'day', 'hour',]):
                # sort group on date
                dt = item['_id']['date']
                key = [_datepart_functions.get(dp)(dt) for dp in dategrouping]
                
                # add remainder elements to sort and group
                for k, v in sorted(item['_id'].items(), key=lambda x:x[0]):
                    if k != 'date':
                        key.append(v)
                return key

            # sort and group [date_parts,...,non-date parts]
            results = sorted(results, key=partial(_date_key, dategrouping=dategrouping))
            groups = groupby(results, key=partial(_date_key, dategrouping=dategrouping))

            def _date_norm(item, datenormalize):
                replace_dict = dict([(k, _date_norm_map.get(k)) for k in datenormalize])
                item['_id']['date'] = item['_id']['date'].replace(**replace_dict)
                return item

            group_fn = sum  # maybe support avg in future
            
            formatted_results = []
            for g in groups:
                item = {}
                items = [i for i in g[1]]

                item.update(items[0])
                item['record_count'] = group_fn([d['record_count'] for d in items])

                item = _date_norm(item, datenormalize)
                formatted_results.append(item)

            if order:
                formatted_results = complex_sorted(formatted_results, order)

            if page and page_size:
                idx = page*page_size
                formatted_results = formatted_results[idx:idx + page_size]

            results = formatted_results

        for item in results:
            new_item = {}
            for k, v in item['_id'].items():
                new_item[unescape_level(k)] = v
            new_item['record_count'] = item['record_count']
            result_items.append(new_item)
        return (None, result_items)

    def _query_conditions_for_cut(self, cut):

        print '=cut', cut, type(cut)

        conds = []
        cut_dimension = self.cube.dimension(cut.dimension)
        cut_hierarchy = cut_dimension.hierarchy(cut.hierarchy)
        if isinstance(cut, PointCut):
            if cut.dimension.lower() == 'date':
                dateparts = ['year', 'month', 'day', 'hour']

                date_dict = {'month': 1, 'day': 1, 'hour':0}
                min_part = None

                for val, dp in zip(cut.path, dateparts[:len(cut.path)]):
                    date_dict[dp] = int(val)
                    min_part = dp

                start = _eastern_date_as_utc(**date_dict)
                end = start + relativedelta(**{dp+'s':1})
                conds.append(self._query_condition_for_path_value(cut_hierarchy.levels[0].key, start, '$gte'))
                conds.append(self._query_condition_for_path_value(cut_hierarchy.levels[0].key, end, '$lt'))

            else:
                # one condition per path element
                for idx, p in enumerate(cut.path):
                    print '=cut', idx, p
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
            if True:
                raise ArgumentError("No support yet for range cuts in mongo2 backend")
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
        phys = self.mapper.physical(attr)
        return phys.match_expression(value, op)

    def _order_to_sort_object(self, order=None):
        if not order:
            return []

        order_by = collections.OrderedDict()
        # each item is a 2-tuple of (logical_attribute_name, sort_order_string)
        for attrname, sort_order_string in order:
            sort_order = -1 if sort_order_string in ('desc', 'DESC') else 1
            attribute = self.mapper.attribute(attrname)

            if attrname not in order_by:
                order_by[escape_level(attribute.ref())] = ( escape_level(attribute.ref()), sort_order )
        return dict( order_by.values() )


def complex_sorted(items, sortings):
    if not sortings or not items:
        return items

    idx, direction = sortings.pop(0)

    if sortings:
        items = complex_sorted(items, sortings)

    return sorted(items, key=lambda x:x.get(idx) or x['_id'].get(idx), reverse=direction in set(['reverse', 'desc', '-1', -1]))


def _eastern_date_as_utc(year, **kwargs):

    dateparts = {'year': year, 'tzinfo': tz}
    dateparts.update(kwargs)

    date = datetime(**dateparts)

    return date.astimezone(tz_utc)


def escape_level(ref):
    return ref.replace('.', '___')


def unescape_level(ref):
    return ref.replace('___', '.')

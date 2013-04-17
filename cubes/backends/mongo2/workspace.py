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
from datesupport import get_date_for_week, calc_week, get_next_weekdate,\
                        datepart_functions, date_norm_map, date_as_utc, so_far_filter


tz = pytz.timezone('America/New_York')
tz_eastern = pytz.timezone('America/New_York')
tz_utc = pytz.timezone('UTC')

__all__ = [
    "create_workspace"
]


def is_date_dimension(dim):
    if isinstance(dim, basestring):
        return 'date' in dim.lower()
    elif hasattr(dim, 'name'):
        return 'date' in dim.name
    else:
        return False

def create_workspace(model, **options):
    return MongoWorkspace(model, **options)


class MongoWorkspace(Workspace):

    def __init__(self, model, **options):
        super(MongoWorkspace, self).__init__(model, **options)
        self.logger = get_logger()
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

    def _json_safe_item(self, item):
        new_item = {}
        for k,v in item.iteritems():
            new_item[k] = str(v) if isinstance(v, bson.objectid.ObjectId) else v
        return new_item

    def facts(self, cell=None, order=None, page=None, page_size=None, **options):
        query_obj, fields_obj = self._build_query_and_fields(cell, [])
        # TODO include fields_obj, fully populated
        cursor = self.data_store.find(query_obj)
        if order:
            order_obj = self._order_to_sort_object(order)
            k, v = order_obj.iteritems().next()
            cursor = cursor.sort(k, pymongo.DESCENDING if v == -1 else pymongo.ASCENDING)
        if page_size and page > 0:
            cursor = cursor.skip(page * page_size)
        if page_size and page_size > 0:
            cursor = cursor.limit(page_size)
        
        # TODO map back to logical values
        items = []
        for item in cursor:
            items.append(self._json_safe_item(item))
        return items

    def fact(self, key):
        # TODO make it possible to have a fact key that is not an ObjectId
        key_field = self.mapper.physical(self.mapper.attribute(self.cube.key))
        key_value = key
        try:
            key_value = bson.objectid.ObjectId(key)
        except:
            pass
        item = self.data_store.find_one({key_field.field: key_value})
        if item is not None:
            item = self._json_safe_item(item)
        return item

    def values(self, cell, dimension, depth=None, paths=None, hierarchy=None, order=None, page=None, page_size=None, **options):
        cell = cell or Cell(self.cube)
        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)
        levels = hierarchy.levels
        if depth is None:
            depth = len(levels)
        if depth < 1 or depth > len(levels):
            raise ArgumentError("depth may not be less than 1 or more than %d, the maximum depth of dimension %s" % (len(levels), dimension.name))
        levels = levels[0:depth]

        level_attributes = []
        for level in levels:
           level_attributes += level.attributes
        summary, cursor = self._do_aggregation_query(cell=cell, measures=None, attributes=level_attributes, drilldown=[(dimension, hierarchy, levels)], order=order, page=page, page_size=page_size)

        data = []
        for item in cursor:
            new_item = {}
            for level in levels:
                # TODO make sure _do_aggregation_query projects all of a level's attributes!
                for level_attr in level.attributes:
                    k = level_attr.ref()
                    if item.has_key(k):
                        new_item[k] = item[k]
            data.append(new_item)

        return data

    def _build_query_and_fields(self, cell, attributes):
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

        return query_obj, fields_obj

    def _do_aggregation_query(self, cell, measures, attributes, drilldown, order, page, page_size):

        # determine query for cell cut
        query_obj, fields_obj = self._build_query_and_fields(cell, attributes)

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
            if dim and is_date_dimension(dim):
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
            datenormalize = ['year', 'month', 'week', 'day', 'hour',]

            date_field = None
            filter_so_far = False
            # calculate correct date:level
            for dim, hier, levels in drilldown:
                if dim and is_date_dimension(dim):
                    date_field = dim.name
                    dategrouping = [str(l).lower() for l in levels]
                    for dg in dategrouping:
                        datenormalize.remove(dg)

                    # TODO don't use magic sofar string
                    if hier.name.lower() == 'sofar':
                        filter_so_far = True
                    break

            def _date_key(item, dategrouping=['year', 'month', 'week', 'day', 'hour',]):
                # sort group on date
                dt = item['_id'][date_field]
                key = [datepart_functions.get(dp)(dt) for dp in dategrouping]
                
                # add remainder elements to sort and group
                for k, v in sorted(item['_id'].items(), key=lambda x:x[0]):
                    if k != date_field:
                        key.append(v)
                return key

            if dategrouping[-1] == 'week':
                dategrouping.remove('year') # year included in week calc because week year might change


            if filter_so_far:
                filt = so_far_filter(datetime.utcnow(), dategrouping[-1], key=lambda x:x['_id'][date_field])
                results = filter(filt, results)


            # sort and group [date_parts,...,non-date parts]
            results = sorted(results, key=partial(_date_key, dategrouping=dategrouping))
            groups = groupby(results, key=partial(_date_key, dategrouping=dategrouping))

            def _date_norm(item, datenormalize, dategrouping):
                dt = item['_id'].pop(date_field)

                if dategrouping[-1] == 'week':
                    dt= get_next_weekdate(dt, direction='up')

                for dp in dategrouping:
                    item['_id']['%s.%s' % (date_field, dp)] = datepart_functions.get(dp)(dt)

                return item

            aggregate_fn = sum  # maybe support avg in future
            
            formatted_results = []
            for g in groups:
                item = {}
                items = [i for i in g[1]]

                item.update(items[0])
                item['record_count'] = aggregate_fn([d['record_count'] for d in items])

                item = _date_norm(item, datenormalize, dategrouping)
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

    def _build_date_for_cut(self, path, tzinfo=tz_eastern):
        dateparts = ['year', 'month', 'day', 'hour']

        date_dict = {'month': 1, 'day': 1, 'hour':0}
        min_part = None

        for val, dp in zip(path, dateparts[:len(path)]):
            date_dict[dp] = int(val)
            min_part = dp

        print '=datedict', date_dict

        # return date_as_utc(**date_dict), min_part
        return datetime(**date_dict), min_part

    def _query_conditions_for_cut(self, cut):
        conds = []
        cut_dimension = self.cube.dimension(cut.dimension)
        cut_hierarchy = cut_dimension.hierarchy(cut.hierarchy)

        if isinstance(cut, PointCut):
            if is_date_dimension(cut.dimension):
                start, dp = self._build_date_for_cut(cut.path)
                end = start + relativedelta(**{dp+'s':1})

                # localize for daylight savings post math
                start = tz_eastern.localize(start)
                end = tz_eastern.localize(end)

                # convert to UTC
                start = start.astimezone(tz_utc)
                end = end.astimezone(tz_utc)

                start_cond = self._query_condition_for_path_value(cut_hierarchy.levels[0].key, start, '$gte' if not cut.invert else '$lt')
                end_cond =self._query_condition_for_path_value(cut_hierarchy.levels[0].key, end, '$lt'if not cut.invert else '$gte')

                if not cut.invert:
                    conds.append(start_cond)
                    conds.append(end_cond)
                else:
                    conds.append({'$or':[start_cond, end_cond]})

            else:
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
            if is_date_dimension(cut.dimension.lower()):
                start_cond = None
                end_cond = None
                if cut.from_path:
                    start, dp = self._build_date_for_cut(cut.from_path)
                    start = tz_eastern.localize(start)
                    start = start.astimezone(tz_utc)
                    start_cond = self._query_condition_for_path_value(cut_hierarchy.levels[0].key, start, '$gte' if not cut.invert else '$lt')
                if cut.to_path:
                    end, dp = self._build_date_for_cut(cut.to_path)
                    end = end + relativedelta(**{dp+'s':1}) # inclusive
                    end = tz_eastern.localize(end)
                    end = end.astimezone(tz_utc)
                    end_cond = self._query_condition_for_path_value(cut_hierarchy.levels[0].key, end, '$lt'if not cut.invert else '$gte')

                if not cut.invert:
                    if start_cond:
                        conds.append(start_cond)
                    if end_cond:
                        conds.append(end_cond)
                else:
                    if start_cond and end_cond:
                        conds.append({'$or':[start_cond, end_cond]})
                    elif start_cond:
                        conds.append(start_cond)
                    elif end_cond:
                        conds.append(end_cond)
                
            if False:
                raise ArgumentError("No support yet for non-date range cuts in mongo2 backend")
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


def escape_level(ref):
    return ref.replace('.', '___')


def unescape_level(ref):
    return ref.replace('___', '.')

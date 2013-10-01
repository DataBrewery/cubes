from ...common import get_logger
from ...errors import *
from ...browser import *
from ...computation import *
from ...statutils import calculators_for_aggregates, available_calculators
from cubes import statutils
from .mapper import MongoCollectionMapper, coalesce_physical
from .datesupport import DateSupport
from .functions import get_aggregate_function, available_aggregate_functions

import collections
import copy
import pymongo
import bson
import re
import time

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from itertools import groupby
from functools import partial
import pytz


tz_utc = pytz.timezone('UTC')


SO_FAR_DIMENSION_REGEX = re.compile(r"^.+_sf$", re.IGNORECASE)

def is_date_dimension(dim):
    if isinstance(dim, basestring):
        return 'date' in dim.lower()
    elif hasattr(dim, 'name'):
        return 'date' in dim.name
    else:
        return False

class Mongo2Browser(AggregationBrowser):
    def __init__(self, cube, store, locale=None, metadata={}, url=None, **options):
        super(Mongo2Browser, self).__init__(cube, store)

        self.logger = get_logger()

        database = store.database
        if cube.browser_options.get('database'):
            database = cube.browser_options.get('database')

        collection = store.collection
        if cube.browser_options.get('collection'):
            collection = cube.browser_options.get('collection')

        self.data_store = store.client[database][collection]

        self.mapper = MongoCollectionMapper(cube, database, collection, locale)

        self.timezone = pytz.timezone(cube.browser_options.get('timezone') or options.get('timezone') or 'UTC')

        self.datesupport = DateSupport(self.logger, self.timezone, options.get('week_start_weekday'))


    def features(self):
        """Return SQL features."""

        features = {
            # TODO: missing "cell"
            "actions": ["aggregate", "members", "fact", "facts"],
            "aggregate_functions": available_aggregate_functions(),
            "post_aggregate_functions": available_calculators()
        }

        return features

    def set_locale(self, locale):
        self.mapper.set_locale(locale)

    def aggregate(self, cell=None, measures=None, aggregates=None,
                  drilldown=None, split=None, attributes=None, order=None,
                  page=None, page_size=None, **options):

        cell = cell or Cell(self.cube)

        aggregates = self.prepare_aggregates(aggregates, measures)
        result = AggregationResult(cell=cell, aggregates=aggregates)

        drilldown_levels = None

        labels = []

        # Prepare the drilldown
        # FIXME: this is the exact code as in SQL browser - put it into a
        # separate method and share

        if drilldown or split:
            if drilldown:
                drilldown = levels_from_drilldown(cell, drilldown)
            else:
                drilldown = []

            dim_levels = {}

            if split:
                dim_levels[SPLIT_DIMENSION_NAME] = split.to_dict().get('cuts')

            for dditem in drilldown:
                dim, hier, levels = dditem.dimension, dditem.hierarchy, dditem.levels

                # if dim or one of its levels is high_cardinality, and there is
                # no page_size and page, raise BrowserError
                if dim.info.get('high_cardinality') \
                        and not (page_size and page is not None):
                    raise BrowserError("Cannot drilldown on high-cardinality "
                                       "dimension (%s) without including "
                                       "both page_size and page arguments" %
                                       (dim.name))

                hc_levels = [ l for l in levels if l.info.get('high_cardinality') ]

                if hc_levels and not (page_size and page is not None):
                    raise BrowserError("Cannot drilldown on high-cardinality "
                                       "levels (%s) without including both "
                                       "page_size and page arguments" %
                                       (",".join([l.key.ref() for l in
                                                  dditem.levels if
                                                  l.info.get('high_cardinality')])))

                dim_levels[str(dim)] = [str(level) for level in levels]

            result.levels = dim_levels

            #
            # Find post-aggregation calculations and decorate the result
            #
            result.calculators = calculators_for_aggregates(aggregates,
                                                            drilldown,
                                                            split,
                                                            available_aggregate_functions())

        summary, items = self._do_aggregation_query(cell=cell,
                                                    aggregates=aggregates,
                                                    attributes=attributes,
                                                    drilldown=drilldown_levels,
                                                    split=split, order=order,
                                                    page=page,
                                                    page_size=page_size)
        result.cells = iter(items)
        result.summary = summary
        # add calculated measures w/o drilldown or split if no drilldown or split
        if not (drilldown or split):
            calculators = calculators_for_aggregates(aggregates, drilldown,
                                                     split,
                                                     available_aggregate_functions())
            for calc in calculators:
                calc(result.summary)

        labels += [ str(m) for m in aggregates ]
        result.labels = labels
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
        summary, cursor = self._do_aggregation_query(cell=cell, aggregates=None,
                                                     attributes=level_attributes,
                                                     drilldown=[(dimension,
                                                                 hierarchy,
                                                                 levels)],
                                                     order=order, page=page,
                                                     page_size=page_size)

        data = []
        for item in cursor:
            new_item = {}
            for level in levels:
                for level_attr in level.attributes:
                    k = level_attr.ref()
                    if item.has_key(k):
                        new_item[k] = item[k]
            data.append(new_item)

        return data

    def _in_same_collection(self, physical_ref):
        return (physical_ref.database == self.mapper.database) and (physical_ref.collection == self.mapper.collection)

    def _measure_aggregation_field(self, logical_ref, aggregation_name):
        if aggregation_name == 'identity':
            return logical_ref
        return "%s_%s" % (logical_ref, aggregation_name)

    def _build_query_and_fields(self, cell, attributes, for_project=False):
        find_clauses = []
        query_obj = {}
        if not for_project and self.cube.mappings and self.cube.mappings.get('__query__'):
            query_obj.update(copy.deepcopy(self.cube.mappings['__query__']))

        find_clauses = reduce(lambda i, c: i + c, [self._query_conditions_for_cut(cut, for_project) for cut in cell.cuts], [])

        if find_clauses:
            query_obj.update({ "$and": find_clauses })

        fields_obj = {}
        if attributes:
            for attribute in attributes:
                phys = self.mapper.physical(attribute)
                if not self._in_same_collection(phys):
                    raise ValueError("Cannot fetch field that is in different collection than this browser: %r" % phys)
                fields_obj[ escape_level(attribute.ref()) ] = phys.project_expression()

        return query_obj, fields_obj

    def _do_aggregation_query(self, cell, aggregates, attributes, drilldown,
                              split, order, page, page_size):

        # determine query for cell cut
        query_obj, fields_obj = self._build_query_and_fields(cell, attributes)

        # If no drilldown or split, only one measure, and only aggregations to
        # do on it are count or identity, no aggregation pipeline needed.
        if not aggregates:
            raise ArgumentError("No aggregates provided.")

        if (not drilldown and not split) \
                and len(aggregates) == 1 \
                and aggregates[0].function in ("count", "identity"):

            return (self.data_store.find(query_obj).count(), [])

        group_id = {}

        # prepare split-related projection of complex boolean condition
        if split:
            split_query_like_obj, dummy = self._build_query_and_fields(split,
                                                                       [],
                                                                       for_project=True)
            if split_query_like_obj:
                fields_obj[escape_level(SPLIT_DIMENSION_NAME)] = split_query_like_obj
                group_id[escape_level(SPLIT_DIMENSION_NAME)] = "$%s" % escape_level(SPLIT_DIMENSION_NAME)

        # drilldown, fire up the pipeline

        timezone_shift_processing = False
        date_transform = lambda x:x

        sort_obj = bson.son.SON()

        if drilldown:
            for dditem in drilldown:
                dim, hier, levels = dditem.dimension, dditem.hierarchy, dditem.levels

                # Special Mongo Date Hack for TZ Support
                if dim and is_date_dimension(dim):
                    is_utc = (self.timezone == tz_utc)
                    phys = self.mapper.physical(levels[0].key)
                    date_idx = phys.project_expression()

                    # add to $match and $project expressions
                    query_obj.update(phys.match_expression(1, op='$exists'))
                    fields_obj[date_idx[1:]] = 1

                    if is_utc and not ([l for l in levels if l.name == 'week']):
                        possible_groups = {
                            'year': {'$year': date_idx},
                            'month': {'$month': date_idx},
                            'day': {'$dayOfMonth': date_idx},
                            'hour': {'$hour': date_idx},
                            'minute': {'$minute': date_idx}
                        }
                        for lvl in levels:
                            group_id[escape_level(lvl.key.ref())] = possible_groups[lvl.name]
                            sort_obj["_id." + escape_level(lvl.key.ref())] = 1

                    else:
                        timezone_shift_processing = True
                        group_id.update({
                            'year': {'$year': date_idx},
                            'month': {'$month': date_idx},
                            'day': {'$dayOfMonth': date_idx},
                            'hour': {'$hour': date_idx}
                        })
                        if levels[-1] == 'minute':
                            group_id['minute'] = { '$minute': date_idx }

                        def _date_transform(item, date_field):
                            date_dict = {}
                            for k in ['year', 'month', 'day', 'hour', 'minute']:
                                if item['_id'].has_key(k):
                                    date_dict[k] = item['_id'].pop(k)

                            date = datetime(**date_dict)
                            date = tz_utc.localize(date)
                            date = date.astimezone(tz=self.timezone) # convert to browser timezone

                            item['_id'][date_field] = date
                            return item

                        date_transform = partial(_date_transform, date_field=dim.name)

                else:
                    for level in levels:
                        key_phys = self.mapper.physical(level.key)
                        sort_obj["_id." + escape_level(level.key.ref())] = 1
                        query_obj.update(key_phys.match_expression(1, op='$exists'))
                        # this loop will include key
                        for attr in level.attributes:
                            fields_obj[escape_level(attr.ref())] = self.mapper.physical(attr).project_expression()
                            group_id[escape_level(attr.ref())] = "$%s" % escape_level(attr.ref())

        group_obj = { "_id": group_id }

        aggregate_fn_pairs = []

        for agg in aggregates:
            try:
                function = get_aggregate_function(agg.function)
            except KeyError:
                continue

            phys = self.mapper.physical(agg)
            fields_obj[escape_level(agg.ref())] = phys.project_expression()

            if not self._in_same_collection(phys):
                raise BrowserError("Measure cannot be in different database "
                                   "or collection than browser: %r" % phys)

            aggregate_fn_pairs.append( ( escape_level(agg.ref()), sum ) )


            if phys.group:
                group = phys.group
            else:
                group_applicator = function["group_by"]
                group = group_applicator(escape_level(agg.ref()))

            group_obj[ escape_level(agg.ref()) ] = group

        pipeline = []
        pipeline.append({ "$match": query_obj })
        if fields_obj:
            pipeline.append({ "$project": fields_obj })
        pipeline.append({ "$group": group_obj })

        if not timezone_shift_processing:
            if order:
                pipeline.append({ "$sort": self._order_to_sort_object(order) })
            elif len(sort_obj):
                pipeline.append({ "$sort": sort_obj })

        if not timezone_shift_processing and page and page > 0:
            pipeline.append({ "$skip": page * page_size })

        if not timezone_shift_processing and page_size and page_size > 0:
            pipeline.append({ "$limit": page_size })

        result_items = []
        self.logger.debug("PIPELINE: %s", pipeline)

        results = self.data_store.aggregate(pipeline).get('result', [])
        results = [date_transform(r) for r in results]

        if timezone_shift_processing:
            dategrouping = ['year', 'month', 'week', 'day', 'hour', 'minute']
            datenormalize = ['year', 'month', 'week', 'dow', 'day', 'hour', 'minute']

            date_field = None
            filter_so_far = False
            # calculate correct date:level
            for dditem in drilldown:
                if dditem.dimension and is_date_dimension(dditem.dimension):
                    date_field = dditem.dimension.name
                    dategrouping = [str(l).lower() for l in dditem.levels]
                    for dg in dategrouping:
                        datenormalize.remove(dg)

                    # TODO don't use magic _sf string for sofar
                    if SO_FAR_DIMENSION_REGEX.match(dditem.dimension.name):
                        filter_so_far = True
                    break

            def _date_key(item, dategrouping=['year', 'month', 'week', 'day', 'hour', 'minute']):
                # sort group on date
                dt = item['_id'][date_field]
                key = [self.datesupport.datepart_functions.get(dp)(dt) for dp in dategrouping]

                # add remainder elements to sort and group
                for k, v in sorted(item['_id'].items(), key=lambda x:x[0]):
                    if k != date_field:
                        key.append(v)
                return key

            if dategrouping[-1] == 'week' and 'year' in dategrouping:
                dategrouping.remove('year') # year included in week calc because week year might change


            if filter_so_far:
                filt = self.datesupport.so_far_filter(datetime.utcnow(), dategrouping[-1], key=lambda x:x['_id'][date_field])
                results = filter(filt, results)


            # sort and group [date_parts,...,non-date parts]
            results = sorted(results, key=partial(_date_key, dategrouping=[ ("dow_sort" if x == "dow" else x) for x in dategrouping ]))
            groups = groupby(results, key=partial(_date_key, dategrouping=dategrouping))

            def _date_norm(item, datenormalize, dategrouping):
                dt = item['_id'].pop(date_field)

                if dategrouping[-1] == 'week':
                    dt= self.datesupport.get_week_end_date(dt)

                for dp in dategrouping:
                    item['_id']['%s.%s' % (date_field, dp)] = self.datesupport.datepart_functions.get(dp)(dt)

                return item

            formatted_results = []
            for g in groups:
                item = {}
                items = [i for i in g[1]]

                item.update(items[0])

                for agg_fn_pair in aggregate_fn_pairs:
                    item[ agg_fn_pair[0] ] = agg_fn_pair[1]([d[ agg_fn_pair[0] ] for d in items])

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
            for agg_fn_pair in aggregate_fn_pairs:
                new_item[ unescape_level(agg_fn_pair[0]) ] = item [ agg_fn_pair[0] ]
            result_items.append(new_item)

        return (None, result_items) if (drilldown or split) else (result_items[0], [])

    def _build_date_for_cut(self, hier, path, is_end=False):
        date_dict = {'month': 1, 'day': 1, 'hour': 0, 'minute': 0 }
        min_part = None

        for val, dp in zip(path, hier.levels[:len(path)]):
            date_dict[dp.key.name] = self.mapper.physical(dp.key).type(val)
            min_part = dp


        dt = None
        if 'year' not in date_dict:
            if 'week' not in date_dict:
                return dt, min_part
            else:
                dt = datetime.strptime(date_dict['week'], '%Y-%m-%d')
                dt = (self.datesupport.get_week_end_date if is_end else self.datesupport.get_week_start_date)(dt)
        else:
            dt = datetime(**date_dict)

        return self.timezone.localize(dt).astimezone(tz_utc), min_part

    def _query_conditions_for_cut(self, cut, for_project=False):
        conds = []
        cut_dimension = self.cube.dimension(cut.dimension)
        cut_hierarchy = cut_dimension.hierarchy(cut.hierarchy)

        if isinstance(cut, PointCut):
            if is_date_dimension(cut.dimension):
                start, dp = self._build_date_for_cut(cut_hierarchy, cut.path)
                if start is None:
                    return conds
                end = start + relativedelta(**{str(dp)+'s':1})

                start_cond = self._query_condition_for_path_value(cut_hierarchy.levels[0].key, start, '$gte' if not cut.invert else '$lt', for_project)
                end_cond =self._query_condition_for_path_value(cut_hierarchy.levels[0].key, end, '$lt'if not cut.invert else '$gte', for_project)

                if not cut.invert:
                    conds.append(start_cond)
                    conds.append(end_cond)
                else:
                    conds.append({'$or':[start_cond, end_cond]})

            else:
                # one condition per path element
                for idx, p in enumerate(cut.path):
                    conds.append( self._query_condition_for_path_value(cut_hierarchy.levels[idx].key, p, "$ne" if cut.invert else '$eq', for_project) )
        elif isinstance(cut, SetCut):
            for path in cut.paths:
                path_conds = []
                for idx, p in enumerate(path):
                    path_conds.append( self._query_condition_for_path_value(cut_hierarchy.levels[idx].key, p, "$ne" if cut.invert else '$eq', for_project) )
                conds.append({ "$and" : path_conds })
            conds = [{ "$or" : conds }]
        # FIXME for multi-level range: it's { $or: [ level_above_me < value_above_me, $and: [level_above_me = value_above_me, my_level < my_value] }
        # of the level value.
        elif isinstance(cut, RangeCut):
            if is_date_dimension(cut.dimension.lower()):
                start_cond = None
                end_cond = None
                if cut.from_path:
                    start, dp = self._build_date_for_cut(cut_hierarchy, cut.from_path)
                    if start is not None:
                        start_cond = self._query_condition_for_path_value(cut_hierarchy.levels[0].key, start, '$gte' if not cut.invert else '$lt', for_project)
                if cut.to_path:
                    end, dp = self._build_date_for_cut(cut_hierarchy, cut.to_path, is_end=True)
                    end = end + relativedelta(**{str(dp)+'s':1}) # inclusive
                    if end is not None:
                        end_cond = self._query_condition_for_path_value(cut_hierarchy.levels[0].key, end, '$lt' if not cut.invert else '$gte', for_project)

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
                        op = ( ("$lt", "$ne") if cut.invert else ("$gte", "$eq") )[0 if idx == last_idx else 1]
                        conds.append( self._query_condition_for_path_value(cut.dimension, p, op, for_project))
                if cut.to_path:
                    last_idx = len(cut.to_path) - 1
                    for idx, p in enumerate(cut.to_path):
                        op = ( ("$gt", "$ne") if cut.invert else ("$lte", "$eq") )[0 if idx == last_idx else 1]
                        conds.append( self._query_condition_for_path_value(cut.dimension, p, "$gt" if cut.invert else "$lte", for_project) )
        else:
            raise ValueError("Unrecognized cut object: %r" % cut)
        return conds

    def _query_condition_for_path_value(self, attr, value, op=None, for_project=False):
        phys = self.mapper.physical(attr)
        return phys.match_expression(value, op, for_project)

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

# -*- encoding: utf-8 -*-
"""Slicer – Cubes command-line tool

For more information run: slicer --help

To enable full user exception debugging set the ``CUBES_ERROR_DEBUG``
environment variable.
"""

from __future__ import absolute_import
from __future__ import print_function

import json
import os
import sys
import click
import cubes

from .. import compat

from ..datastructures import AttributeDict
from ..errors import InconsistencyError, ArgumentError, InternalError, UserError
from ..formatters import csv_generator, SlicerJSONEncoder, JSONLinesGenerator
from ..metadata import read_model_metadata, write_model_metadata_bundle
from ..workspace import Workspace
from ..errors import CubesError
from ..server import run_server
from ..server.base import read_slicer_config

from .. import ext

from ..cells import cuts_from_string, Cell
from ..browser import string_to_dimension_level


DEFAULT_CONFIG = "slicer.ini"


@click.group()
@click.pass_context
@click.option('--debug/--no-debug',
              envvar='CUBES_DEBUG',
              default=False,
              help="Enable/disable debugging output")
def cli(ctx, debug):
    ctx.obj = AttributeDict()
    ctx.obj.debug = debug


################################################################################
# Command: serve

@cli.command()
@click.argument('config', type=click.Path(exists=True), default=DEFAULT_CONFIG)
@click.option('--visualizer',
              help="Visualizer URL for /visualizer path")
@click.pass_context
def serve(ctx, config, visualizer):
    """Run Slicer HTTP server."""
    config = read_config(config)

    # FIXME: "visualizer" shouldn't be in "server" section
    if visualizer:
        config.set("server", "visualizer", visualizer)

    run_server(config, debug=ctx.obj.debug)

################################################################################
# Command: extension

@cli.command("ext-info")
@click.argument('extension_type', metavar='TYPE', required=False, default='all')
@click.argument('extension_name', metavar='NAME', required=False)
@click.pass_context
def extension_info(ctx, extension_type, extension_name):
    """Show info about Cubes extensions"""

    if extension_type == 'all':
        types = ext.EXTENSION_TYPES.items()
    else:
        label = ext.EXTENSION_TYPES[extension_type]
        types = [(extension_type, label)]

    if extension_name:
        # Print detailed extension information
        manager = getattr(ext, extension_type)
        extension = manager.get(extension_name)
        extension.load()

        desc = extension.description or "No description."
        click.echo("{e.name} - {e.label}\n\n"
                   "{desc}\n"
                   .format(e=extension, desc=desc))

        if extension.options:
            click.echo("Configuration options:\n")

            for option in extension.options.values():
                name = option.get("name")
                desc = option.get("description", option.get("label"))
                desc = " - {}".format(desc) if desc else ""
                type_ = option.get("type_", "string")

                click.echo("    {name} ({type_}){desc}"
                           .format(name=name, desc=desc,
                                   type_=type_))
        else:
            click.echo("No known options.")
    else:
        # List extensions
        click.echo("Available Cubes extensions:\n")
        for ext_type, _ in types:
            manager = getattr(ext, ext_type)
            manager.discover()
            names = manager.names()

            click.echo("{}:\n    {}\n".format(ext_type, ", ".join(names)))

    click.echo()

################################################################################
# Command: list

@cli.command()
@click.option('--verbose/--terse', 'verbose', default=False,
              help='Display also cube description')
@click.argument('config', required=False,
                default=DEFAULT_CONFIG, type=click.Path(exists=True))
@click.pass_context
def list(ctx, config, verbose):
    """List cubes"""
    ws = Workspace(config)

    for cube in ws.list_cubes():
        name = cube["name"]
        label = cube.get("label", name)
        desc = cube.get("description", "(no description)")
        if verbose:
            print("{} - {}\n    {}\n".format(name, label, desc))
        else:
            print("{} - {}".format(name, label))


################################################################################
# Command: valdate_model

@cli.group()
@click.pass_context
def model(ctx):
    """Model metadata tools."""
    pass

@model.command()
@click.option('--defaults', '-d', 'show_defaults', default=False,
              help='show defaults')
@click.option('--warnings/--no-warnings', 'show_warnings', default=True,
              help='enable/disable warnings')
@click.argument('model_path', metavar='MODEL')
def validate(show_defaults, show_warnings, model_path):
    """Validate model metadata"""

    click.echo("Reading model %s" % model_path)
    model = cubes.read_model_metadata(model_path)

    click.echo("Validating model...")
    result = cubes.providers.validate_model(model)

    error_count = 0
    warning_count = 0
    default_count = 0

    for error in result:
        if error.scope == "model":
            scope = "model"
        else:
            if error.object:
                scope = "%s '%s'" % (error.scope, error.object)
            else:
                scope = "unknown %s" % error.scope

        if error.property:
            scope += " property '%s'" % error.property

        show = True
        if error.severity == "error":
            error_count += 1
        elif error.severity == "warning":
            warning_count += 1
            show = show_warnings
        elif error.severity == "default":
            show = show_defaults
            default_count += 1

        if show:
            print("%s in %s: %s"
                  % (error.severity.upper(), scope, error.message))

    if error_count == 0:
        if warning_count == 0:
            if default_count == 0:
                verdict = "model can be used"
            else:
                verdict = "model can be used, " \
                          "make sure that the defaults reflect reality"
        else:
            verdict = "not recommended to use the model, " \
                      "some issues might emerge"
    else:
        verdict = "model can not be used"

    print("")
    print("Defaults used  %d" % default_count)
    print("Warning        %d" % warning_count)
    print("Errors         %d" % error_count)
    print("Summary        %s" % verdict)

    if error_count > 0:
        exit(1)

################################################################################
# Command: test

@cli.command()
@click.option('--aggregate', is_flag=True, default=False,
              help="Test aggregate of whole cube")
@click.option('--exclude-store', '-E', 'exclude_stores', multiple=True)
@click.option('--store', 'include_stores', multiple=True)
@click.argument('config', default=DEFAULT_CONFIG)
@click.argument('cube', nargs=-1)
def test(aggregate, exclude_stores, include_stores, config, cube):
    """Test every cube in the model"""
    workspace = cubes.Workspace(config)

    errors = []

    if cube:
        cube_list = cube
    else:
        cube_list = [c["name"] for c in workspace.list_cubes()]

    exclude = exclude_stores or []
    include = include_stores or []

    tested = 0

    for name in cube_list:
        cube = workspace.cube(name)

        click.echo("testing {}: ".format(name), nl=False)

        if cube.store_name in exclude \
                or (include and cube.store_name not in include):
            click.echo("pass")
            continue

        try:
            browser = workspace.browser(name)
        except Exception as e:
            errors.append((name, e))
            click.echo("BROWSER ERROR")
            continue

        tested += 1

        try:
            facts = browser.test(aggregate=aggregate)
        except NotImplementedError:
            click.echo("pass - no test")
        # FIXME XXX CubesError not defined
        except CubesError as e:
            errors.append((name, e))
            click.echo("ERROR")

    click.echo()
    click.echo("tested %d cubes" % tested)

    if errors:
        click.echo("%d ERRORS:" % len(errors))
        for (cube, e) in errors:
            if hasattr(e, "error_type"):
                etype = e.error_type
            else:
                etype = str(type(e))

            click.echo("%s: %s - %s" % (cube, etype, str(e)))
    else:
        click.echo("test passed")


@model.command()
@click.option('--format', 'model_format', type=click.Choice(["json", "bundle"]),
              default='json',
              help='output model format')
@click.option('--force', is_flag=True,
              default=False,
              help='replace existing model bundle')
@click.argument('model_path', metavar='MODEL')
@click.argument('target', required=False)
@click.pass_context
def convert(ctx, model_format, force, model_path, target):
    """Convert model between model formats."""

    metadata = read_model_metadata(model_path)
    if model_format == "json":
        if not target:
            print(json.dumps(metadata, indent=4))
        else:
            with open(target, "w") as f:
                json.dump(metadata, f, indent=4)
    elif model_format == "bundle":
        write_model_metadata_bundle(target, metadata, replace=force)

def read_config(cfg):
    """Read the configuration file."""
    return read_slicer_config(cfg)

################################################################################
# Group: sql

@cli.group()
@click.pass_context
@click.option('--store', nargs=1,
              help="Name of the store to use other than default. Must be SQL.")
@click.option('--config', nargs=1, default=DEFAULT_CONFIG,
              help="Name of slicer.ini configuration file")
def sql(ctx, store, config):
    """SQL store commands"""
    ctx.obj.workspace = cubes.Workspace(config)
    ctx.obj.store = ctx.obj.workspace.get_store(store)

################################################################################
# Command: sql denormalize

@sql.command()
@click.option('--force', is_flag=True, default=False,
              help='replace existing views')
@click.option('--materialize', '-m', is_flag=True, default=False,
              help='create materialized view (table)')
@click.option('--index/--no-index', default=True,
              help='create index for key attributes')
@click.option('--schema', '-s',
              help='target view schema (overrides default fact schema')
@click.argument('cube', required=False)
@click.argument('target', required=False)
@click.pass_context
def denormalize(ctx, force, materialize, index, schema, cube, target):
    """Create denormalized view(s) from cube(s)."""

    if not materialize and index:
        raise ArgumentError("Non-materialized views can't be indexed")

    # Shortcuts
    workspace = ctx.obj.workspace
    store = ctx.obj.store

    if cube:
        target = target or store.naming.denormalized_table_name(cube)
        cubes = [(cube, target)]
    else:
        names = workspace.cube_names()
        targets = [store.naming.denormalized_table_name(name)
                   for name in names]
        cubes = zip(names, targets)

    for cube_name, target in cubes:
        cube = workspace.cube(cube_name)
        store = workspace.get_store(cube.store_name or "default")

        print("denormalizing cube '%s' into '%s'" % (cube_name,
                                                     target))

        store.create_denormalized_view(cube, target,
                                       materialize=materialize,
                                       replace=force,
                                       create_index=index,
                                       keys_only=False,
                                       schema=schema)


# TODO: Nice to have it back
# @sql.command("ddl")
# @click.argument('cubes', required=False, nargs=-1)
# @click.pass_context
# def generate_ddl(ctx, cubes):
#     # Shortcuts
#     workspace = ctx.obj.workspace
#     store = ctx.obj.store
#
#     ddl = store.ddl_for_model(args.url, model, fact_prefix=args.fact_prefix,
#                                 dimension_prefix=args.dimension_prefix,
#                                 fact_suffix=args.fact_suffix,
#                                 dimension_suffix=args.dimension_suffix)
#
#     print(ddl)


################################################################################
# Command: sql aggregate

@sql.command("aggregate")
@click.option('--force', is_flag=True, default=False,
              help='replace existing views')
@click.option('--index/--no-index', default=True,
              help='create index for key attributes')
@click.option('--schema', '-s',
              help='target view schema (overrides default fact schema')
@click.option('--dimension', '-d', "dimensions", multiple=True,
              help='dimension to be used for aggregation')
@click.argument('cube', required=False)
@click.argument('target', required=False)
@click.pass_context
def sql_aggregate(ctx, force, index, schema, cube, target, dimensions):
    """Create pre-aggregated table from cube(s). If no cube is specified, then
    all cubes are aggregated. Target table can be specified only for one cube,
    for multiple cubes naming convention is used.
    """
    workspace = ctx.obj.workspace
    store = ctx.obj.store

    if cube:
        target = target or store.naming.aggregated_table_name(cube)
        cubes = [(cube, target)]
    else:
        names = workspace.cube_names()
        targets = [store.naming.aggregated_table_name(name)
                   for name in names]
        cubes = zip(names, targets)

    for cube_name, target in cubes:
        cube = workspace.cube(cube_name)
        store = workspace.get_store(cube.store_name or "default")

        print("denormalizing cube '%s' into '%s'" % (cube_name,
                                                     target))

        store.create_cube_aggregate(cube, target,
                                    replace=force,
                                    create_index=index,
                                    schema=schema,
                                    dimensions=dimensions)


################################################################################
# Command: aggregate

@cli.command()
@click.option('--config', type=click.Path(exists=True), required=False,
              default=DEFAULT_CONFIG)

@click.option('--aggregate', '-a', 'aggregates', multiple=True,
              help="List of aggregates to get")
@click.option('--cut', '-c', 'cuts', multiple=True,
              help="Cell cut")
@click.option('--split', 'split_str', multiple=False,
              help="Split cell")
@click.option('--drilldown', '-d', 'drilldown', multiple=True,
              help="Drilldown dimensions")

@click.option('--on-row', 'on_rows', multiple=True,
              help="Attribute to put on row (default is all)")
@click.option('--on-column', 'on_columns', multiple=True,
              help="Attribute to put on column (default is none)")

@click.option('--format', "-f", "formatter_name", default="cross_table",
              help="Output format")

@click.argument('cube_name', metavar='CUBE')
@click.pass_context
def aggregate(ctx, config, cube_name, aggregates, cuts, drilldown, formatter_name,
              split_str, on_rows, on_columns):
    """Aggregate a cube"""
    config = read_config(config)
    workspace = Workspace(config)
    browser = workspace.browser(cube_name)

    cell_cuts = []
    for cut_str in cuts:
        cell_cuts += cuts_from_string(browser.cube, cut_str)

    cell = Cell(browser.cube, cell_cuts)

    split_cuts = cuts_from_string(browser.cube, split_str)
    if split_cuts:
        split = Cell(browser.cube, split_cuts)
    else:
        split = None

    if not aggregates:
        aggregates = [agg.name for agg in browser.cube.aggregates]

    # TODO: paging and ordering
    result = browser.aggregate(cell,
                               aggregates=aggregates,
                               drilldown=drilldown,
                               split=split,
                               page=None,
                               page_size=None,
                               order=None)

    if formatter_name:
        formatter = ext.formatter(formatter_name)
        output = formatter.format(browser.cube,
                                  result,
                                  onrows=on_rows,
                                  oncolumns=on_columns,
                                  aggregates=aggregates,
                                  aggregates_on="columns")
    else:
        output = result.to_dict()

    click.echo(output)


################################################################################
# Command: members

@cli.command()
@click.option('--config', type=click.Path(exists=True), required=False,
              default=DEFAULT_CONFIG)

@click.option('--cut', '-c', 'cuts', multiple=True,
              help="Cell cut")

@click.option('--format', "-f", "output_format", default="json",
              type=click.Choice(["json", "csv", "json_lines" ]),
              help="Output format")

@click.argument('cube_name', metavar='CUBE')
@click.argument('dim_name', metavar='DIMENSION')
@click.pass_context
def members(ctx, config, cube_name, cuts, dim_name, output_format):
    """Aggregate a cube"""
    config = read_config(config)
    workspace = Workspace(config)
    browser = workspace.browser(cube_name)
    cube = browser.cube

    cell_cuts = []
    for cut_str in cuts:
        cell_cuts += cuts_from_string(browser.cube, cut_str)

    cell = Cell(browser.cube, cell_cuts)

    (dim_name, hier_name, level_name) = string_to_dimension_level(dim_name)
    dimension = cube.dimension(dim_name)
    hierarchy = dimension.hierarchy(hier_name)

    if level_name:
        depth = hierarchy.level_index(level_name) + 1
    else:
        depth = len(hierarchy)

    # TODO: pagination
    values = browser.members(cell,
                             dimension,
                             depth=depth,
                             hierarchy=hierarchy,
                             page=None,
                             page_size=None)

    attributes = []
    for level in hierarchy.levels_for_depth(depth):
        attributes += level.attributes

    fields = [attr.ref for attr in attributes]
    labels = [attr.label or attr.name for attr in attributes]

    if output_format == "json":
        encoder = SlicerJSONEncoder(indent=4)
        result = encoder.iterencode(values)
    elif output_format == "json_lines":
        result = JSONLinesGenerator(values)
    elif output_format == "csv":
        result = csv_generator(values,
                               fields,
                               include_header=True,
                               header=labels)

    out = click.get_text_stream('stdout')
    for row in result:
        out.write(row)


def main(*args, **kwargs):

    try:
        cli(*args, **kwargs)

    except InconsistencyError as e:
        # Internal Error - error caused by some edge case conditio, misbehaved
        # cubes or wrongly categorized error
        #
        # It is very unlikely that the user might fix this error by changing
        # his/her input.
        #
        if os.environ.get("CUBES_ERROR_DEBUG"):
            raise
        else:
            click.echo("\n" \
                  "Error: Internal error occured.\n"
                  "Reason: {}\n\n" \
                  "Please report the error and information about what you " \
                  "were doing to the Cubes development team.\n"
                  .format(e), err=True)
            sys.exit(1)

    except (InternalError, UserError) as e:
        # Error caused by the user – model or data related.
        #
        # User can fix the error by altering his/her input.
        #
        if os.environ.get("CUBES_ERROR_DEBUG"):
            raise
        else:
            click.echo("\nError: {}".format(e), err=True)
            sys.exit(1)


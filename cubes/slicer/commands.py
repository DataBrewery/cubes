# -*- encoding: utf-8 -*-

"""Slicer tool

    For more information run: slicer --help

    Author: Stefan Urbanek <stefan.urbanek@gmail.com>
    Date: 2011-01
"""

from __future__ import absolute_import
from __future__ import print_function

from .. import compat

import click
import json
import sys
import os
import cubes

from collections import OrderedDict

from ..common import MissingPackageError
from ..logging import create_logger
from ..errors import CubesError, ArgumentError
from ..metadata import read_model_metadata, write_model_metadata_bundle
from .. import server
from ..datastructures import AttributeDict
from ..workspace import Workspace

try:
    from cubes_modeler import ModelEditorSlicerCommand
except ImportError:
    ModelEditorSlicerCommand = None


@click.group()
@click.pass_context
@click.option('--debug/--no-debug', envvar='CUBES_DEBUG', default=False)
def cli(ctx, debug):
    ctx.obj = AttributeDict()
    ctx.obj.debug = debug


################################################################################
# Command: serve

@cli.command()
@click.argument('config', type=click.Path(exists=True), default="slicer.ini")
@click.option('--visualizer',
              help="Visualizer URL or 'default' for built-in visualizer")
@click.pass_context
def serve(ctx, config, visualizer):
    """Run Slicer HTTP server."""
    config = read_config(config)

    if config.has_option("server", "pid_file"):
        path = config.get("server", "pid_file")
        try:
            with open(path, "w") as f:
                f.write("%s\n" % os.getpid())
        except IOError:
            raise CubesError("Unable to write PID file '%s'. Check the "
                             "directory existence or permissions." % path)

    if visualizer:
        config.set("server", "visualizer", visualizer)

    cubes.server.run_server(config, debug=True)
    # TODO cubes.server.run_server(config, debug=ctx.debug)

################################################################################
# Command: serve

@cli.command()
@click.option('--verbose/--terse', 'verbose', default=False,
              help='Display also cube description')
@click.argument('config', required=False,
                default="slicer.ini", type=click.Path(exists=True))
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
@click.argument('config')
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

        sys.stdout.write("testing %s: " % name)

        if cube.store_name in exclude \
                or (include and cube.store_name not in include):
            sys.stdout.write("pass\n")
            continue

        try:
            browser = workspace.browser(name)
        except Exception as e:
            errors.append((name, e))
            sys.stdout.write("BROWSER ERROR\n")
            continue

        tested += 1

        try:
            facts = browser.test(aggregate=aggregate)
        except NotImplementedError:
            sys.stdout.write("pass - no test\n")
        except CubesError as e:
            errors.append((name, e))
            sys.stdout.write("ERROR\n")

    print("\ntested %d cubes" % tested)
    if errors:
        print("%d ERRORS:" % len(errors))
        for (cube, e) in errors:
            if hasattr(e, "error_type"):
                etype = e.error_type
            else:
                etype = str(type(e))

            print("%s: %s - %s" % (cube, etype, str(e)))
    else:
        print("test passed")


@model.command()
@click.option('--format', type=click.Choice(["json", "bundle"]),
              default='json',
              help='output model format')
@click.option('--force', is_flag=True,
              default=False,
              help='replace existing model bundle')
@click.argument('model_path', metavar='MODEL')
@click.argument('target', required=False)
@click.pass_context
def convert(ctx, format, force, model_path, target):
    """Convert model between model formats."""

    metadata = read_model_metadata(model_path)
    if format == "json":
        if not target:
            print(json.dumps(metadata, indent=4))
        else:
            with open(path, "w") as f:
                json.dump(metadata, f, indent=4)
    elif args.format == "bundle":
        write_model_metadata_bundle(path, metadata, replace=force)

def read_config(cfg):
    """Read the configuration file."""
    config = compat.ConfigParser()
    try:
        config.read(cfg)
    except Exception as e:
        raise Exception("Unable to load config: %s" % e)

    return config

################################################################################
# Group: sql

@cli.group()
@click.pass_context
@click.option('--store', nargs=1,
              help="Name of the store to use other than default. Must be SQL.")
@click.option('--config', nargs=1, default="slicer.ini",
              help="Name of slicer.ini configuration file")
def sql(ctx, store, config):
    """SQL store commands"""
    ctx.obj.workspace = cubes.Workspace(config)
    ctx.obj.store = ctx.obj.workspace.get_store(store)

################################################################################
# Command: denormalize

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
        view_name = store.naming.denormalized_table_name(cube_name)

        print("denormalizing cube '%s' into '%s'" % (cube_name,
                                                     target))

        store.create_cube_aggregate(cube, target,
                                            replace=force,
                                            create_index=index,
                                            schema=schema,
                                            dimensions=dimensions)

def edit_model(args):
    if not run_modeler:
        sys.stderr.write("ERROR: 'cubes_modeler' package needs to be "
                         "installed to edit the model.\n")
        exit(1)

    if args.port:
        port = int(args.port)
    else:
        port = 5000

    import webbrowser
    webbrowser.open("http://127.0.0.1:%s" % port)

    run_modeler(args.model, args.target)

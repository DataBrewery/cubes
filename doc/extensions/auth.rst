******************************
Authenticators and Authorizers
******************************

.. seealso::

    :doc:`plugins`

Authorizer
==========

Authorizers gives or denies access to cubes and restricts access to a portion
of a cube.

Custom authorizers should be subclasses of :class:`cubes.Authorizer` (to be
findable) and should have the following methods:

* `authorize(identity, cubes)` – return list of cube names (from the `cubes`)
  that the `identity` is allowed to acces. Might return an empty list if no
  cubes are allowed.
* `restricted_cell(identity, cube, cell)` – return a cell derived from `cell`
  with restrictions for `identity`

Custom authorizer example: an authorizer that uses some HTTP service that
accepts list of cubes in the ``cubes=`` paramter and returns a comma separated
list of authorized cubes.

.. code-block:: python

    class CustomAuthorizer(Authorizer):
        def __init__(self, url=None, user_dimension=None, **options):
            super(DatabaseAuthorizer, self).__init__(self, **options)

            self.url = url
            self.user_dimension = user_dimension or "user"

        def authorize(self, cubes):
            params = {
                "cubes": ",".join(cubes)
            }

            response = Request(url, params=params)

            return response.data.split(",")

.. note::

    The custom authorizer has to be a subclass of `Authorizer` so Cubes can
    find it. The name will be derived from the class name: `CustomAuthorizer`
    will become `custom`, `DatabaseACLAuthorizer` will become `database_acl`.
    To explicitly specify an authorizer name, set the `__extension_name__` class
    variable.


The cell restrictions are handled by `restricted_cell()` method which receives
the identity, cube object (not just a name) and optionaly the cell to be
restricted.

.. code-block:: python

    class CustomAuthorizer(Authorizer):
        def __init__(self, url=None, table=None, **options):
            # ... initialization goes here ...

        def authorize(self, cubes):
            # ... authorization goes here
            return cubes

        def restricted_cell(self, identity, cube, cell):

            # If the cube has no dimension "user", we can't restrict
            # and we assume that the cube can be seen by anyone

            try:
                cube.dimension(self.user_dimension)
            except NoSuchDimensionError:
                return cell

            # Find the user ID based on identity
            user_id = self.find_user(identity)

            # Assume a flat "user" dimension for every cube
            cut = PointCut(self.user_dimension, [user_id])
            restriction = Cell(cube, [cut])

            if cell:
                return cell & restriction
            else:
                return restriction



Configuration
-------------

The authorizer is configured from the ``[authorization]`` section in the
`slicer.ini` file. The authorizer instance receives all options from the
section as arguments to the `__init__()` method.

To use the above authorizer, add the following to the ``slicer.ini``:

.. code-block:: ini

    [workspace]
    authorization: custom

    [authorization]
    url: http://localhost/authorization_service
    user_dimension: user


Authenticator
=============

Authentication takes place at the server level right before a request is
processed.

Custom authenticator has to be a subclass of
:class:`slicer.server.Authenticator` and has to have at least
`authenticate(request)` method defined. Another optional method is
`logout(request, identity)`.

Example authenticator which authenticates against a database table with two
columns: `user` and `password` with a clear-text password (don't do that).

.. code-block:: python

    from cubes.server import Authenticator, NotAuthenticated
    from sqlalchemy import create_engine, MetaData, Table

    class DatabaseAuthenticator(Authenticator):
        def __init__(self, url=None, table=None, **options):

            self.engine = create_engine(url)
            metadata = MetaData(bind=engine)
            self.users = Table(table, metadata, autoload=True)

        def authenticate(self, request):
            user = request.values.get("user")
            password = request.values.get("password")

            select = self.users.select(self.users.c.password)
            select = select.where(self.users.c.user == user)

            row = self.engine.execute(select).fetchone()

            if row["password"] == password:
                return user
            else:
                raise NotAuthenticated

The `authenticate(request)` method should return the identity that will be
later passed to the authorizer (it does not have to be the same value as a
user name). The identity might even be `None` which might be interpreted by
some authorizers guest or not-logged-in visitor. The method should raise
`NotAuthenticated` when the credetials don't match.



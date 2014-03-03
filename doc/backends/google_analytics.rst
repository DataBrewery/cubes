************************
Google Analytics Backend
************************

Package Requirements
--------------------

Required packages:

* `google-api-python-client`
* `openssl`
* `httplib2`

store configuration and model
=============================

Requirements
------------

Google Analytics bakend uses `Service Account
<https://developers.google.com/console/help/new/#serviceaccounts>`_ access
type to the Google API. Required is *Email address* and the public key file.

To get the required credentials go to the `Google Developers Console
<https://cloud.google.com/console>`_, then *APIs & auth* and then select
*Credentials*. If you don't have a key already press the *Create New Client
ID* button and select *Service Account* option. Don't forget to download the
private key file.

.. note::

    The email address you need is the email address generated for the *Service
    Account*, not your account email address. 


Add the generated service account email address to the list of permissions in
the Account User Management in the Google Analytics Admin page.

Configuration
-------------

type is ``ga``

* ``email`` (required) – email address of the service account
* ``key_file`` (required) – path to a private key file of the service account
* ``account_id`` – ID of the account to be used
* ``account_name`` – name of the account to be used
* ``web_property`` – web property ID (first will be used by default)
* ``view_id`` – Reporting view (profile) ID (first will be used by default) 
* ``category`` – category of cubes (property and view name will be used as
  default)

* ``default_start_date`` – start date to be used if no bottom date range is
  specified. Format: ``yyyy-mm-dd``
* ``default_end_date`` – end date to be used if no end date is specified.
  Format: ``yyyy-mm-dd``.

Specify either ``account_id`` or ``account_name``, not both. If none is
specified then the first account in the account list is used.

Example::

    [store]
    type: ga
    email: 123456789012-abcdefghijklmnopqrstuvwxyzabcdef@developer.gserviceaccount.com
    key_file: key.p12
    web_property: UA-123456-7

Model
-----

Google Analytics backend generates the model on-the-fly using the Analytics
API.  You have to specify that the provider is ``ga`` not the static model
file itself:

.. code-block:: javascript

    {
        "provider": "ga"
    }


Armada - Rollback
=================


Commands
--------

.. code:: bash

    Usage: armada rollback [OPTIONS]

    This command performs a rollback on the specified release.

    To rollback a release, run:

        $ armada rollback --release my_release

    Options:
      --dry-run                     Perform a dry-run rollback.
      --release TEXT                Release to rollback.
      --tiller-host TEXT            Tiller Host IP
      --tiller-port INTEGER         Tiller Host Port
      -tn, --tiller-namespace TEXT  Tiller Namespace
      --timeout INTEGER             Tiller Host IP
      --version INTEGER             Version of release to rollback to. 0 represents the previous release
      --wait                        Version of release to rollback to. 0 represents the previous release
      --help                        Show this message and exit.

Synopsis
--------

The rollback command will perform helm rollback on the release.

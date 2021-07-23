Armada - Apply
==============


Commands
--------

.. code:: bash

    Usage: armada apply [OPTIONS] [LOCATIONS]...

      This command installs and updates charts defined in Armada manifest.

      The apply argument must be relative path to Armada Manifest. Executing
      apply command once will install all charts defined in manifest. Re-
      executing apply command will execute upgrade.

      To see how to create an Armada manifest:     https://airship-
      armada.readthedocs.io/en/latest/operations/

      To install or upgrade charts, run:

              $ armada apply examples/simple.yaml

      To override a specific value in a Manifest, run:

              $ armada apply examples/simple.yaml --set manifest:simple-armada:release="wordpress"

      Or to override several values in a Manifest, reference a values.yaml-
      formatted file:

              $ armada apply examples/simple.yaml --values examples/simple-ovr-values.yaml

    Options:
      --api                         Contacts service endpoint.
      --disable-update-post         Disable post-update Helm operations.
      --disable-update-pre          Disable pre-update Helm operations.
      --enable-chart-cleanup        Clean up unmanaged charts.
      --metrics-output TEXT         The output path for metric data
      --use-doc-ref                 Use armada manifest file reference.
      --set TEXT                    Use to override Armada Manifest values.
                                    Accepts overrides that adhere to the format
                                    <path>:<to>:<property>=<value> to specify a
                                    primitive or
                                    <path>:<to>:<property>=<value1>,...,<valueN>
                                    to specify a list of values.
      --timeout INTEGER             Specifies time to wait for each chart to fully
                                    finish deploying.
      -f, --values TEXT             Use to override multiple Armada Manifest
                                    values by reading overrides from a
                                    values.yaml-type file.
      --wait                        Force Helm to wait until all charts are
                                    deployed, rather than using each charts
                                    specified wait policy. This is equivalent to
                                    sequenced chartgroups.
      --target-manifest TEXT        The target manifest to run. Required for
                                    specifying which manifest to run when multiple
                                    are available.
      --bearer-token TEXT           User Bearer token
      --debug                       Enable debug logging.
      --help                        Show this message and exit.

Synopsis
--------

The apply command will consume an armada manifest which contains group of charts
that it will deploy via the Helm CLI into your Kubernetes cluster.
Executing the ``armada apply`` again on existing armada deployment will start
an update of the armada deployed charts.

``armada apply armada-manifest.yaml [--debug]``

If you remove ``armada/Charts/v1`` from the ``armada/ChartGroups/v1`` in the armada
manifest and execute an ``armada apply`` with the  ``--enable-chart-cleanup`` flag.
Armada will remove undefined releases with the armada manifest's
``release_prefix`` keyword.

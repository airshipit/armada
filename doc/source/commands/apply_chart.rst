Armada - Apply Chart
====================


Commands
--------

.. code:: bash

    Usage: armada apply_chart [OPTIONS] [LOCATION]

      This command installs and updates an Armada chart.

      [LOCATION] must be a relative path to Armada Chart or a reference
      to an Armada Chart kubernetes CR which has the same format, except as
      noted in the :ref:`v2 document authoring documentation <document_authoring_v2>`.

      To install or upgrade a chart, run:

              $ armada apply_chart --release-prefix=armada my-chart.yaml
              $ armada apply_chart --release-prefix=armada kube:armadacharts/my-namespace/my-chart

    Options:
      --release-prefix TEXT         Release prefix to use.  [required]
      --disable-update-post         Disable post-update Tiller operations.
      --disable-update-pre          Disable pre-update Tiller operations.
      --metrics-output TEXT         Output path for prometheus metric data, should
                                    end in .prom. By default, no metric data is
                                    output.
      --tiller-host TEXT            Tiller host IP.
      --tiller-port INTEGER         Tiller host port.
      -tn, --tiller-namespace TEXT  Tiller namespace.
      --timeout INTEGER             Specifies time to wait for each chart to fully
                                    finish deploying.
      --wait                        Force Tiller to wait until the chart is
                                    deployed, rather than using the charts
                                    specified wait policy. This is equivalent to
                                    sequenced chartgroups.
      --target-chart TEXT           The target chart to deploy. Required for
                                    specifying which chart to deploy when multiple
                                    are available.
      --bearer-token TEXT           User Bearer token
      --debug                       Enable debug logging.
      --help                        Show this message and exit.

Synopsis
--------

The apply_chart command will deploy an armada chart definition, installing or
updating as appropriate.

``armada apply_chart --release-prefix=armada my-chart.yaml [--debug]``
``armada apply_chart --release-prefix=armada kube:armadacharts/my-namespace/my-chart [--debug]``

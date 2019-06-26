.. _metrics:

Metrics
=======

Armada exposes metric data, for consumption by `Prometheus`_.

Exporting
---------

Metric data can be exported via:

  * API: Prometheus exporter in the `/metrics` endpoint. The Armada chart
    includes the appropriate Prometheus scrape configurations for this endpoint.
  * CLI: `--metrics-output=<path>` of `apply` command. The
    `node exporter text file collector`_ can then be used to export the produced
    text files to Prometheus.

Metric Names
------------

Metric names are as follows:

`armada_` + <action> + `_` + <metric>

Supported <action>s
-------------------

The below tree of <action>s are measured. Supported prometheus labels are noted.
Labels are inherited by sub-actions except as noted.

  * `apply`:

    * description: apply a manifest
    * labels: `manifest`
    * sub-actions:

      * `chart_handle`:

        * description: fully handle a chart (see below sub-actions)
        * labels:

          * `chart`
          * `action` (install|upgrade|noop) (not included in sub-actions)
        * sub-actions:

          * `chart_download`
          * `chart_deploy`
          * `chart_test`
      * `chart_delete`:

        * description: delete a chart (e.g. due to `FAILED` status)
        * labels: `chart`

Supported <metric>s
-------------------

  * `failure_total`: total failed attempts
  * `attempt_total`: total attempts
  * `attempt_inprogress`: total attempts in progress
  * `duration_seconds`: duration of each attempt

Timeouts
^^^^^^^^

The `chart_handle` and `chart_test` actions additionally include the following
metrics:

  * `timeout_duration_seconds`: configured chart timeout duration in seconds
  * `timeout_usage_ratio`: `= duration_seconds / timeout_duration_seconds`

These can help identify charts whose timeouts may need to
be changed to avoid potential failures or to acheive faster failures.

Chart concurrency
^^^^^^^^^^^^^^^^^

The `chart_handle` action additionally includes the following metric:

  * `concurrency_count`: count of charts being handled concurrently

This can help identify opportunities for greater chart concurrency.

.. _Prometheus: https://prometheus.io
.. _`node exporter text file collector`: https://github.com/prometheus/node_exporter#textfile-collector

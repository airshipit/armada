..
  Copyright 2019 AT&T Intellectual Property.
  All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License"); you may
  not use this file except in compliance with the License. You may obtain
  a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
  License for the specific language governing permissions and limitations
  under the License.

.. _document_authoring_v2:

v2 Authoring
============

.. DANGER::

    EXPERIMENTAL: `v2` docs are still experimental and WILL have breaking changes
    before they are finalized.

armada/Manifest/v2
------------------

+---------------------+--------+-------------------------+
| keyword             | type   | action                  |
+=====================+========+=========================+
| ``release_prefix``  | string | appends to the          |
|                     |        | front of all            |
|                     |        | charts                  |
|                     |        | released                |
|                     |        | by the                  |
|                     |        | manifest in             |
|                     |        | order to                |
|                     |        | manage releases         |
|                     |        | throughout their        |
|                     |        | lifecycle               |
+---------------------+--------+-------------------------+
| ``chart_groups``    | array  | A list of the           |
|                     |        | ``metadata.name`` of    |
|                     |        | each ``ChartGroup`` to  |
|                     |        | deploy in order.        |
+---------------------+--------+-------------------------+

Manifest Example
^^^^^^^^^^^^^^^^

::

    ---
    schema: armada/Manifest/v2
    metadata:
      schema: metadata/Document/v1
      name: simple-armada
    data:
      release_prefix: armada
      chart_groups:
        - chart_group


armada/ChartGroup/v2
--------------------

+-----------------+----------+------------------------------------------------------------------------+
| keyword         | type     | action                                                                 |
+=================+==========+========================================================================+
| description     | string   | description of chart set                                               |
+-----------------+----------+------------------------------------------------------------------------+
| chart_group     | array    | A list of the ``metadata.name`` of each ``Chart`` to deploy.           |
+-----------------+----------+------------------------------------------------------------------------+
| sequenced       | bool     | If ``true``, deploys each chart in sequence, else in parallel.         |
|                 |          | Default ``false``.                                                     |
+-----------------+----------+------------------------------------------------------------------------+

Chart Group Example
^^^^^^^^^^^^^^^^^^^

::

    ---
    schema: armada/ChartGroup/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-group
    data:
      description: Deploys Simple Service
      chart_group:
        - chart1
        - chart2

armada/Chart/v2
---------------

Chart
^^^^^

+-----------------+----------+---------------------------------------------------------------------------------------+
| keyword         | type     | action                                                                                |
+=================+==========+=======================================================================================+
| release         | string   | name of the release (Armada will prepend with ``release-prefix`` during processing)   |
+-----------------+----------+---------------------------------------------------------------------------------------+
| namespace       | string   | namespace of your chart                                                               |
+-----------------+----------+---------------------------------------------------------------------------------------+
| wait            | object   | See `Wait`_.                                                                          |
+-----------------+----------+---------------------------------------------------------------------------------------+
| protected       | object   | do not delete FAILED releases when encountered from previous run (provide the         |
|                 |          | 'continue_processing' bool to continue or halt execution (default: halt))             |
+-----------------+----------+---------------------------------------------------------------------------------------+
| test            | object   | See Test_.                                                                            |
+-----------------+----------+---------------------------------------------------------------------------------------+
| upgrade         | object   | upgrade the chart managed by the armada yaml                                          |
+-----------------+----------+---------------------------------------------------------------------------------------+
| delete          | object   | See Delete_.                                                                          |
+-----------------+----------+---------------------------------------------------------------------------------------+
| values          | object   | (optional) override any default values in the charts                                  |
+-----------------+----------+---------------------------------------------------------------------------------------+
| source          | object   | provide a path to a ``git repo``, ``local dir``, or ``tarball url`` chart             |
+-----------------+----------+---------------------------------------------------------------------------------------+
| dependencies    | object   | (optional) reference any chart dependencies before install                            |
+-----------------+----------+---------------------------------------------------------------------------------------+

Wait
^^^^

+-------------+----------+--------------------------------------------------------------------+
| keyword     | type     | action                                                             |
+=============+==========+====================================================================+
| timeout     | int      | time (in seconds) to wait for chart to deploy                      |
+-------------+----------+--------------------------------------------------------------------+
| resources   | array    | Array of `Wait Resource`_ to wait on, with ``labels`` added to each|
|             |          | item. Defaults to pods and jobs (if any exist) matching ``labels``.|
+-------------+----------+--------------------------------------------------------------------+
| labels      | object   | Base mapping of labels to wait on. They are added to any labels in |
|             |          | each item in the ``resources`` array.                              |
+-------------+----------+--------------------------------------------------------------------+
| native      | boolean  | See `Wait Native`_.                                                |
+-------------+----------+--------------------------------------------------------------------+

Wait Resource
^^^^^^^^^^^^^
+-------------+----------+--------------------------------------------------------------------+
| keyword     | type     | action                                                             |
+=============+==========+====================================================================+
| type        | string   | k8s resource type, supports: controllers ('deployment',            |
|             |          | 'daemonset', 'statefulset'), 'pod', 'job'                          |
+-------------+----------+--------------------------------------------------------------------+
| labels      | object   | mapping of kubernetes resource labels                              |
+-------------+----------+--------------------------------------------------------------------+
| min\_ready  | int      | Only for controller ``type``s. Amount of pods in a controller      |
|             | string   | which must be ready. Can be integer or percent string e.g. ``80%``.|
|             |          | Default ``100%``.                                                  |
+-------------+----------+--------------------------------------------------------------------+

Wait Native
^^^^^^^^^^^

Config for the native ``helm (install|upgrade) --wait`` flag.

+-------------+----------+--------------------------------------------------------------------+
| keyword     | type     | action                                                             |
+=============+==========+====================================================================+
| enabled     | boolean  | defaults to true                                                   |
+-------------+----------+--------------------------------------------------------------------+

.. _test_v2:

Test
^^^^

Run helm tests on the chart after install/upgrade.

+-------------+----------+--------------------------------------------------------------------+
| keyword     | type     | action                                                             |
+=============+==========+====================================================================+
| enabled     | bool     | whether to enable/disable helm tests for this chart (default True) |
+-------------+----------+--------------------------------------------------------------------+
| timeout     | int      | time (in sec) to wait for completion of Helm tests                 |
+-------------+----------+--------------------------------------------------------------------+
| options     | object   | See `Test Options`_.                                               |
+-------------+----------+--------------------------------------------------------------------+

.. note::

    Armada will attempt to run helm tests by default. They may be disabled by
    setting the ``enabled`` key to ``False``.

Test Options
^^^^^^^^^^^^

Test options to pass through directly to helm.

+-------------+----------+---------------------------------------------------------------+
| keyword     | type     | action                                                        |
+=============+==========+===============================================================+
| cleanup     | bool     | cleanup test pods after test completion, defaults to false    |
+-------------+----------+---------------------------------------------------------------+

.. note::

    If cleanup is ``true`` this prevents being able to debug a test in the event of failure.

    Historically, the preferred way to achieve test cleanup has been to add a pre-upgrade delete
    action on the test pod.

    This still works, however it is usually no longer necessary as Armada now automatically
    cleans up any test pods which match the ``wait.labels`` of the chart, immediately before
    running tests. Similar suggestions have been made for how ``helm test --cleanup`` itself
    ought to work (https://github.com/helm/helm/issues/3279).

Upgrade - Pre
^^^^^^^^^^^^^

+-------------+----------+---------------------------------------------------------------+
| keyword     | type     | action                                                        |
+=============+==========+===============================================================+
| pre         | object   | actions performed prior to updating a release                 |
+-------------+----------+---------------------------------------------------------------+

Upgrade - Actions
^^^^^^^^^^^^^^^^^

+-------------+----------+---------------------------------------------------------------+
| keyword     | type     | action                                                        |
+=============+==========+===============================================================+
| delete      | array    | List of `Upgrade - Actions - Delete`_.                        |
+-------------+----------+---------------------------------------------------------------+

Upgrade - Actions - Delete
^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------+----------+---------------------------------------------------------------+
| keyword     | type     | action                                                        |
+=============+==========+===============================================================+
| type        | string   | type of kubernetes resource to delete                         |
|             |          | supported types are: 'pod', 'job', 'cronjob'.                 |
+-------------+----------+---------------------------------------------------------------+
| labels      | object   | k:v mapping of labels to select Kubernetes resources          |
+-------------+----------+---------------------------------------------------------------+

Chart Example
^^^^^^^^^^^^^

::

    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      release: blog-1
      namespace: default
      wait:
        timeout: 100
      protected:
        continue_processing: false
      test:
        enabled: true
      upgrade:
        pre:
          delete:
            - name: test-job
              type: job
              labels:
                foo: bar
                component: bar
                rak1: enabled
      source:
        type: git
        location: https://github.com/namespace/repo
        reference: master

Delete
^^^^^^

+-------------+----------+-----------------------------------------------------------------------------------+
| keyword     | type     | action                                                                            |
+=============+==========+===================================================================================+
| timeout     | integer  | time (in seconds) to wait for chart to be deleted                                 |
+-------------+----------+-----------------------------------------------------------------------------------+

Source
^^^^^^

+-------------+----------+-----------------------------------------------------------------------------------+
| keyword     | type     | action                                                                            |
+=============+==========+===================================================================================+
| type        | string   | source to build the chart: ``git``, ``local``, or ``tar``                         |
+-------------+----------+-----------------------------------------------------------------------------------+
| location    | string   | ``url`` or ``path`` to the chart's parent directory                               |
+-------------+----------+-----------------------------------------------------------------------------------+
| subpath     | string   | (optional) relative path to target chart from parent (``.`` if not specified)     |
+-------------+----------+-----------------------------------------------------------------------------------+
| reference   | string   | (optional) branch, commit, or reference in the repo (``master`` if not specified) |
+-------------+----------+-----------------------------------------------------------------------------------+

Source Example
^^^^^^^^^^^^^^

::

    # type git
    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      release: blog-1
      namespace: default
      wait:
        timeout: 100
        labels:
          component: blog
      source:
        type: git
        location: https://github.com/namespace/repo

    # type local
    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      release: blog-1
      namespace: default
      wait:
        timeout: 100
      source:
        type: local
        location: /path/to/charts
        subpath: chart
        reference: master

    # type tar
    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      release: blog-1
      namespace: default
      wait:
        timeout: 100
      source:
        type: tar
        location: https://localhost:8879/charts/chart-0.1.0.tgz
        subpath: mariadb

Simple Example
^^^^^^^^^^^^^^

::

    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      release: blog-1
      namespace: default
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: blog-1
        reference: new-feat
    ---
    schema: armada/ChartGroup/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-group
    data:
      description: Deploys Simple Service
      chart_group:
        - blog-1
    ---
    schema: armada/Manifest/v2
    metadata:
      schema: metadata/Document/v1
      name: simple-armada
    data:
      release_prefix: armada
      chart_groups:
        - blog-group

Multichart Example
^^^^^^^^^^^^^^^^^^

::

    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      release: blog-1
      namespace: default
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: blog1
        reference: master
    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-2
    data:
      release: blog-2
      namespace: default
      source:
        type: tar
        location: https://github.com/namespace/repo/blog2.tgz
        subpath: blog2
    ---
    schema: armada/Chart/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-3
    data:
      release: blog-3
      namespace: default
      source:
        type: local
        location: /home/user/namespace/repo/blog3
    ---
    schema: armada/ChartGroup/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-group-1
    data:
      description: Deploys Simple Service
      chart_group:
        - blog-2
    ---
    schema: armada/ChartGroup/v2
    metadata:
      schema: metadata/Document/v1
      name: blog-group-2
    data:
      description: Deploys Simple Service
      chart_group:
        - blog-1
        - blog-3
    ---
    schema: armada/Manifest/v2
    metadata:
      schema: metadata/Document/v1
      name: simple-armada
    data:
      release_prefix: armada
      chart_groups:
        - blog-group-1
        - blog-group-2

References
~~~~~~~~~~

For working examples please check the examples in our repo
`here <https://github.com/openstack/airship-armada/tree/master/examples>`__

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

.. _document_authoring_v1:

v1 Authoring
============

armada/Manifest/v1
------------------

+---------------------+--------+----------------------+
| keyword             | type   | action               |
+=====================+========+======================+
| ``release_prefix``  | string | appends to the       |
|                     |        | front of all         |
|                     |        | charts               |
|                     |        | released             |
|                     |        | by the               |
|                     |        | manifest in          |
|                     |        | order to             |
|                     |        | manage releases      |
|                     |        | throughout their     |
|                     |        | lifecycle            |
+---------------------+--------+----------------------+
| ``chart_groups``    | array  | references           |
|                     |        | ChartGroup document  |
|                     |        | of all groups        |
|                     |        |                      |
+---------------------+--------+----------------------+

Manifest Example
^^^^^^^^^^^^^^^^

::

    ---
    schema: armada/Manifest/v1
    metadata:
      schema: metadata/Document/v1
      name: simple-armada
    data:
      release_prefix: armada
      chart_groups:
        - chart_group


armada/ChartGroup/v1
--------------------

+-----------------+----------+------------------------------------------------------------------------+
| keyword         | type     | action                                                                 |
+=================+==========+========================================================================+
| description     | string   | description of chart set                                               |
+-----------------+----------+------------------------------------------------------------------------+
| chart_group     | array    | reference to chart document                                            |
+-----------------+----------+------------------------------------------------------------------------+
| sequenced       | bool     | enables sequenced chart deployment in a group                          |
+-----------------+----------+------------------------------------------------------------------------+
| test_charts     | bool     | run pre-defined helm tests in a ChartGroup (DEPRECATED)                |
+-----------------+----------+------------------------------------------------------------------------+

.. DANGER::

    DEPRECATION: The ``test_charts`` key will be removed, as Armada will run
    helm tests for all charts by default.


Chart Group Example
^^^^^^^^^^^^^^^^^^^

::

    ---
    schema: armada/ChartGroup/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-group
    data:
      description: Deploys Simple Service
      sequenced: False
      chart_group:
        - chart
        - chart

armada/Chart/v1
---------------

.. DANGER::

    DEPRECATION: ``timeout`` key-value will be removed timeout will be defined
    under ``wait`` object.


Chart
^^^^^

+-----------------+----------+---------------------------------------------------------------------------------------+
| keyword         | type     | action                                                                                |
+=================+==========+=======================================================================================+
| chart\_name     | string   | name for the chart                                                                    |
+-----------------+----------+---------------------------------------------------------------------------------------+
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
| install         | object   | install the chart into your Kubernetes cluster                                        |
+-----------------+----------+---------------------------------------------------------------------------------------+
| upgrade         | object   | upgrade the chart managed by the armada yaml                                          |
+-----------------+----------+---------------------------------------------------------------------------------------+
| delete          | object   | See Delete_.                                                                          |
+-----------------+----------+---------------------------------------------------------------------------------------+
| values          | object   | override any default values in the charts                                             |
+-----------------+----------+---------------------------------------------------------------------------------------+
| source          | object   | provide a path to a ``git repo``, ``local dir``, or ``tarball url`` chart             |
+-----------------+----------+---------------------------------------------------------------------------------------+
| dependencies    | object   | (optional) Override the `builtin chart dependencies`_ with a list of Chart documents  |
|                 |          | to use as dependencies instead.                                                       |
|                 |          | NOTE: Builtin ".tgz" dependencies are not yet supported.                              |
+-----------------+----------+---------------------------------------------------------------------------------------+
| timeout         | int      | time (in seconds) allotted for chart to deploy when 'wait' flag is set (DEPRECATED)   |
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

Test
^^^^

Run helm tests on the chart after install/upgrade.

+-------------+----------+--------------------------------------------------------------------+
| keyword     | type     | action                                                             |
+=============+==========+====================================================================+
| enabled     | bool     | whether to enable/disable helm tests for this chart (default True) |
+-------------+----------+--------------------------------------------------------------------+
| timeout     | int      | time (in sec) to wait for completion of Helm tests. Default 300.   |
+-------------+----------+--------------------------------------------------------------------+
| options     | object   | See `Test Options`_.                                               |
+-------------+----------+--------------------------------------------------------------------+

.. note::

    Armada will attempt to run helm tests by default. They may be disabled by
    setting the ``enabled`` key to ``False``.

.. DANGER::

    DEPRECATION: In addition to an object with the above fields, the ``test``
    key currently also supports ``bool``, which maps to ``enabled``, but this is
    deprecated and will be removed.  The ``cleanup`` option below is set to true
    in this case for backward compatibility.

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
| update      | object   | update daemonsets in pre-upgrade update actions               |
+-------------+----------+---------------------------------------------------------------+
| delete      | sequence | delete jobs and pods in pre-upgrade delete actions            |
+-------------+----------+---------------------------------------------------------------+

Upgrade - Actions - Update/Delete
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------+----------+---------------------------------------------------------------+
| keyword     | type     | action                                                        |
+=============+==========+===============================================================+
| name        | string   | name of action                                                |
+-------------+----------+---------------------------------------------------------------+
| type        | string   | type of Kubernetes workload to execute in scope for action    |
+-------------+----------+---------------------------------------------------------------+
| labels      | object   | k:v mapping of labels to select Kubernetes resources          |
+-------------+----------+---------------------------------------------------------------+

.. note::

   Update Actions only support type: 'daemonset'

.. note::

   Delete Actions support type: 'pod', 'job', 'cronjob'

Chart Example
^^^^^^^^^^^^^

::

    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      wait:
        timeout: 100
      protected:
        continue_processing: false
      test:
        enabled: true
      install:
        no_hooks: false
      upgrade:
        no_hooks: false
        pre:
          update:
            - name: test-daemonset
              type: daemonset
              labels:
                foo: bar
                component: bar
                rak1: enabled
          delete:
            - name: test-job
              type: job
              labels:
                foo: bar
                component: bar
                rak1: enabled
      values: {}
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: .
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

+-----------------+----------+-----------------------------------------------------------------------------------+
| keyword         | type     | action                                                                            |
+=================+==========+===================================================================================+
| type            | string   | source to build the chart: ``git``, ``local``, or ``tar``                         |
+-----------------+----------+-----------------------------------------------------------------------------------+
| location        | string   | ``url`` or ``path`` to the chart's parent directory                               |
+-----------------+----------+-----------------------------------------------------------------------------------+
| subpath         | string   | (optional) relative path to target chart from parent (``.`` if not specified)     |
+-----------------+----------+-----------------------------------------------------------------------------------+
| reference       | string   | (optional) branch, commit, or reference in the repo (``master`` if not specified) |
+-----------------+----------+-----------------------------------------------------------------------------------+
| proxy\_server   | string   | (optional) proxy server URL for downloading ``git`` or ``tar`` charts             |
+-----------------+----------+-----------------------------------------------------------------------------------+

Source Example
^^^^^^^^^^^^^^

::

    # type git
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      wait:
        timeout: 100
        labels:
          component: blog
      install:
        no_hooks: false
      upgrade:
        no_hooks: false
      values: {}
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: .
        reference: master

    # type local
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      wait:
        timeout: 100
      install:
        no_hooks: false
      upgrade:
        no_hooks: false
      values: {}
      source:
        type: local
        location: /path/to/charts
        subpath: chart
        reference: master

    # type tar
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      wait:
        timeout: 100
      install:
        no_hooks: false
      upgrade:
        no_hooks: false
      values: {}
      source:
        type: tar
        location: https://localhost:8879/charts/chart-0.1.0.tgz
        subpath: mariadb
        reference: null
        proxy_server: http://my.proxy.server:8888





Defining a Manifest
~~~~~~~~~~~~~~~~~~~

To define your Manifest you need to define a ``armada/Manifest/v1`` document,
``armada/ChartGroup/v1`` document, ``armada/Chart/v1``.
Following the definitions above for each document you will be able to construct
an armada manifest.

Armada - Deploy Behavior
^^^^^^^^^^^^^^^^^^^^^^^^

1. Armada will perform set of pre-flight checks to before applying the manifest
   - validate input manifest
   - check chart source locations are valid

2. Deploying Armada Manifest

   1. If the chart is not found

      -  we will install the chart


   3. If exist then

      -  Armada will check if there are any differences in the chart
      -  if the charts are different then it will execute an upgrade
      -  else it will not perform any actions

.. note::

    You can use references in order to build your charts, this will reduce
    the size of the chart definition will show example in multichart below

Simple Example
^^^^^^^^^^^^^^

::

    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      values: {}
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: blog-1
        reference: new-feat
    ---
    schema: armada/ChartGroup/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-group
    data:
      description: Deploys Simple Service
      sequenced: False
      chart_group:
        - blog-1
    ---
    schema: armada/Manifest/v1
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
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      values: {}
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: blog1
        reference: master
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-2
    data:
      chart_name: blog-2
      release: blog-2
      namespace: default
      values: {}
      source:
        type: tar
        location: https://github.com/namespace/repo/blog2.tgz
        subpath: blog2
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-3
    data:
      chart_name: blog-3
      release: blog-3
      namespace: default
      values: {}
      source:
        type: local
        location: /home/user/namespace/repo/blog3
    ---
    schema: armada/ChartGroup/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-group-1
    data:
      description: Deploys Simple Service
      sequenced: False
      chart_group:
        - blog-2
    ---
    schema: armada/ChartGroup/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-group-2
    data:
      description: Deploys Simple Service
      sequenced: False
      chart_group:
        - blog-1
        - blog-3
    ---
    schema: armada/Manifest/v1
    metadata:
      schema: metadata/Document/v1
      name: simple-armada
    data:
      release_prefix: armada
      chart_groups:
        - blog-group-1
        - blog-group-2

Dependency Override Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1
    data:
      chart_name: blog-1
      release: blog-1
      namespace: default
      values: {}
      source:
        type: git
        location: https://github.com/namespace/repo
        subpath: blog-1
        reference: new-feat
      dependencies:
        - blog-1-dep
    ---
    schema: armada/Chart/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-1-dep
    data:
      chart_name: blog-1-dep
      release: blog-1-dep
      namespace: default
      values: {}
      source:
        type: git
        location: https://github.com/namespace/dep-repo
        subpath: blog-1-dep
        reference: new-feat
    ---
    schema: armada/ChartGroup/v1
    metadata:
      schema: metadata/Document/v1
      name: blog-group
    data:
      description: Deploys Simple Service
      sequenced: False
      chart_group:
        - blog-1
    ---
    schema: armada/Manifest/v1
    metadata:
      schema: metadata/Document/v1
      name: simple-armada
    data:
      release_prefix: armada
      chart_groups:
        - blog-group

References
~~~~~~~~~~

For working examples please check the examples in our repo
`here <https://opendev.org/airship/armada/src/branch/master/examples>`__.

.. _builtin chart dependencies: https://helm.sh/docs/developing_charts/#chart-dependencies

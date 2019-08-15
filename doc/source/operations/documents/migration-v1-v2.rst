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

v1-v2 Migration
===============

The following migrations must be done when moving from :ref:`v1 <document_authoring_v1>` to :ref:`v2 <document_authoring_v2>` docs.

Chart
-----

+--------------------------------+------------------------------------------------------------+
| change                         | migration                                                  |
+================================+============================================================+
| ``chart_name`` removed         | Remove. It was redundant with ``metadata.name`` while at   |
|                                | the same time not guaranteeing uniqueness. Log messages now|
|                                | reference ``metadata.name`` for improved grep-ability.     |
+--------------------------------+------------------------------------------------------------+
| ``test`` as a boolean removed  | :ref:`test <test_v2>` must now be an object.               |
+--------------------------------+------------------------------------------------------------+
| ``timeout`` removed            | Use ``wait.timeout`` instead.                              |
+--------------------------------+------------------------------------------------------------+
| ``install`` removed            | Remove. Previously unused.                                 |
+--------------------------------+------------------------------------------------------------+
| ``upgrade.post`` removed       | Remove.                                                    |
+--------------------------------+------------------------------------------------------------+
| ``upgrade.pre.update`` removed | Remove.                                                    |
+--------------------------------+------------------------------------------------------------+
| ``upgrade.pre.create`` removed | Remove.                                                    |
+--------------------------------+------------------------------------------------------------+
| ``upgrade.pre.delete[*].name`` | Remove.                                                    |
| removed                        |                                                            |
+--------------------------------+------------------------------------------------------------+
| ``upgrade.pre.delete[*]``      | If you have an item in ``upgrade.pre.delete`` and          |
| with ``type: job`` no longer   | ``type: job`` and you also want to delete cronjobs, add    |
| deletes cronjobs               | another item with ``type: cronjob`` and same labels.       |
+--------------------------------+------------------------------------------------------------+
| ``upgrade.no_hooks`` moved to  | Remove as desired, otherwise move to the new location.     |
| ``upgrade.options.no_hooks``,  |                                                            |
| and now optional               |                                                            |
+--------------------------------+------------------------------------------------------------+
| ``source.subpath``             | Remove as desired.                                         |
| now optional, deafults to no   |                                                            |
| subpath.                       |                                                            |
+--------------------------------+------------------------------------------------------------+
| ``wait`` improvements          | See `Wait Improvements`_.                                  |
+--------------------------------+------------------------------------------------------------+

Wait Improvements
^^^^^^^^^^^^^^^^^

The :ref:`v2 wait API <wait_v2>` includes the following changes.

Breaking changes
****************

1. ``wait.resources`` now defaults to all supported resource types,
   currently ``job``, ``daemonset``, ``statefulset``, ``deployment``, and ``pod``, with
   ``required`` (a new option) set to ``false``. The previous default was
   the equivalent of pods with ``required=true``, and jobs with
   ``required=false``.

2. ``type: pod`` waits now exclude pods owned by other resources, such
   as controllers, as one should instead wait directly on the controller itself,
   which per 1. is now the default.

3. Waits are no longer retried due to resources having been modified. This was
   mildly useful before as an indicator of whether all targeted resources were
   accounted for, but with 1. and 2. above, we are now tracking top-level
   resources directly included in the release, rather than generated resources,
   such as controller-owned pods, so there is no need to wait for them to come
   into existence.

4. ``wait.native.enabled`` is now disabled by default. With the above changes,
   this is no longer useful as a backup mechanism. Having both enabled leads to
   ambiguity in which wait would fail in each case. More importantly, this must
   be disabled in order to use the ``min_ready`` functionality, otherwise tiller
   will wait for 100% anyway. So this prevents accidentally leaving it enabled
   in that case. Also when the tiller native wait times out, this caused the
   release to be marked FAILED by tiller, which caused it to be purged and
   re-installed (unless protected), even though the wait criteria may have
   eventually succeeded, which is already validated by armada on a retry.

New features
************

Per-resource-type overrides
+++++++++++++++++++++++++++

``wait.resources`` can now be a dict, mapping individual resource types to
wait configurations (or lists thereof), such that one can keep the default
configuration for the other resource types, and also disable a given resource
type, by mapping it to ``false``.

The ability to provide the entire explicit list for ``wait.resources`` remains in
place as well.

required
++++++++

A ``required`` field is also exposed for items/values in ``wait.resources``.

allow_async_updates
+++++++++++++++++++

An ``allow_async_updates`` field is added to daemonset and statefulset type
items/values in ``wait.resources``.

ChartGroup
----------

+--------------------------+-----------------------------------------------------------+
| change                   | migration                                                 |
+==========================+===========================================================+
| ``test_charts`` removed  | Use the Chart schema's :ref:`test.enabled <test_v2>`      |
|                          | instead.                                                  |
+--------------------------+-----------------------------------------------------------+

Manifest
--------

No changes.

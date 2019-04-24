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
| ``dependencies``,              | Remove as desired.                                         |
| ``source.subpath``             |                                                            |
| now optional                   |                                                            |
+--------------------------------+------------------------------------------------------------+

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

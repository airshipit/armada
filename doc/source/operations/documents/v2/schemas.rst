..
  Copyright 2018 AT&T Intellectual Property.
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

v2 Schemas
==========

Below are the schemas Armada uses to validate Charts, Chart Groups, and
Manifests.

Charts
------

Charts consist of the smallest building blocks in Armada. A ``Chart`` is
comparable to a Helm chart. Charts consist of all the labels, dependencies,
install and upgrade information, hooks and additional information needed to
convey to Tiller.

Chart Groups
------------

A ``Chart Group`` consists of a list of charts. ``Chart Group`` documents are
useful for managing a group of ``Chart`` documents together.

Manifests
---------

A ``Manifest`` is the largest building block in Armada. ``Manifest`` documents
are responsible for managing collections of ``Chart Group`` documents.

Validation Schemas
------------------

Introduction
^^^^^^^^^^^^

All schemas below are `Deckhand DataSchema`_ documents, which are essentially
JSON schemas, with additional metadata useful for Deckhand to perform
`layering`_ and `substitution`_.

The validation schemas below are used by Armada to validate all ingested
Charts, Chart Groups, and Manifests. Use the schemas below as models for
authoring Armada documents.

.. _Deckhand DataSchema: https://docs.airshipit.org/deckhand/document-types.html?highlight=dataschema#dataschema
.. _Helm charts: https://docs.helm.sh/developing_charts/
.. _layering: https://docs.airshipit.org/deckhand/layering.html
.. _substitution: https://docs.airshipit.org/deckhand/substitution.html

Schemas
^^^^^^^

* ``Chart`` schema.

  JSON schema against which all documents with ``armada/Chart/v2``
  ``metadata.name`` are validated.

  .. literalinclude::
    ../../../../../armada/schemas/armada-chart-schema-v2.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``armada/Chart/v2`` documents.

  This schema is used to sanity-check all ``Chart`` documents that are passed
  to Armada.

* ``Chart Group`` schema.

  JSON schema against which all documents with ``armada/Chart/v2``
  ``metadata.name`` are validated.

  .. literalinclude::
    ../../../../../armada/schemas/armada-chartgroup-schema-v2.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``armada/ChartGroup/v2`` documents.

  This schema is used to sanity-check all ``Chart Group`` documents that are
  passed to Armada.

* ``Manifest`` schema.

  JSON schema against which all documents with ``armada/Manifest/v2``
  ``metadata.name`` are validated.

  .. literalinclude::
    ../../../../../armada/schemas/armada-manifest-schema-v2.yaml
    :language: yaml
    :lines: 15-
    :caption: Schema for ``armada/Manifest/v2`` documents.

  This schema is used to sanity-check all ``Manifest`` documents that are passed
  to Armada.

Authoring Guidelines
--------------------

All Armada documents must use the ``deckhand/DataSchema/v1`` schema.

.. todo::

  Expand on this section.

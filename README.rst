Armada
======

|Docker Repository on Quay| |Doc Status|

Armada is a tool for managing multiple Helm charts with dependencies by
centralizing all configurations in a single Armada YAML and providing
life-cycle hooks for all Helm releases.

Find more documentation for Armada on `Read The Docs <https://airship-armada.readthedocs.io/>`_.

Overview
--------

The Armada Python library and command line tool provide a way to
synchronize a Helm (Tiller) target with an operator's intended state,
consisting of several charts, dependencies, and overrides using a single file
or directory with a collection of files. This allows operators to define many
charts, potentially with different namespaces for those releases, and their
overrides in a central place. With a single command, deploy and/or upgrade them
where applicable.

Armada also supports fetching Helm chart source and then building charts from
source from various local and remote locations, such as Git endpoints, tarballs
or local directories.

It will also give the operator some indication of what is about to change by
assisting with diffs for both values, values overrides, and actual template
changes.

Its functionality extends beyond Helm, assisting in interacting with Kubernetes
directly to perform basic pre- and post-steps, such as removing completed or
failed jobs, running backup jobs, blocking on chart readiness, or deleting
resources that do not support upgrades. However, primarily, it is an interface
to support orchestrating Helm.

Components
----------

Armada consists of two separate but complementary components:

#. CLI component (**mandatory**) which interfaces directly with `Tiller`_.
#. API component (**optional**) which services user requests through a wsgi
   server (which in turn communicates with the `Tiller`_ server) and provides
   the following additional functionality:

   * Role-Based Access Control.
   * Limiting projects to specific `Tiller`_ functionality by leveraging
     project-scoping provided by `Keystone`_.

Installation
------------

Quick Start (via Container)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Armada can be most easily installed as a container, which requires Docker to be
executed. To install Docker, please reference the following
`install guide <https://docs.docker.com/engine/installation/>`_.

Afterward, you can launch the Armada container by executing:

.. code-block:: bash

    $ sudo docker run -d --net host -p 8000:8000 --name armada \
        -v ~/.kube/config:/armada/.kube/config \
        -v $(pwd)/examples/:/examples quay.io/airshipit/armada:latest-ubuntu_bionic

Manual Installation
^^^^^^^^^^^^^^^^^^^

For a comprehensive manual installation guide, please
see `Manual Install Guide`_.

Usage
^^^^^

To run Armada, simply supply it with your YAML-based intention for any
number of charts::

  $ armada apply examples/openstack-helm.yaml [ --debug ]

Which should output something like this::

  $ armada apply examples/openstack-helm.yaml 2017-02-10 09:42:36,753

    armada INFO Cloning git:
    ...

For more information on how to install and use Armada, please reference:
`Armada Quickstart`_.


Integration Points
------------------

Armada CLI component has the following integration points:

  * `Tiller`_ manages Armada chart installations.
  * `Deckhand`_ is one of the supported control document sources for Armada.
  * `Prometheus`_ exporter is provided for metric data related to application
    of charts and collections of charts. See `metrics`_.

In addition, Armada's API component has the following integration points:

  * `Keystone`_ (OpenStack's identity service) provides authentication and
    support for role-based authorization.

Further Reading
---------------

`Airship <https://airshipit.org>`_.

.. _Manual Install Guide: https://airship-armada.readthedocs.io/en/latest/development/getting-started.html#developer-install-guide
.. _Armada Quickstart: https://airship-armada.readthedocs.io/en/latest/operations/guide-use-armada.html
.. _metrics: https://airship-armada.readthedocs.io/en/latest/operations/metrics.html#metrics
.. _kubectl: https://kubernetes.io/docs/user-guide/kubectl/kubectl_config/
.. _Tiller: https://docs.helm.sh/using_helm/#easy-in-cluster-installation
.. _Deckhand: https://github.com/openstack/airship-deckhand
.. _Prometheus: https://prometheus.io
.. _Keystone: https://github.com/openstack/keystone

.. |Docker Repository on Quay| image:: https://quay.io/repository/airshipit/armada/status
   :target: https://quay.io/repository/airshipit/armada
.. |Doc Status| image:: https://readthedocs.org/projects/airship-armada/badge/?version=latest
   :target: https://airship-armada.readthedocs.io/

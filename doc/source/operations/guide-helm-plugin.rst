Armada Plugin
=============

The armada plugin extends all the functionality of Armada to be used as a plugin with Helm.

Install Plugin
---------------

**Install directly from the repository**

::

  helm plugin install https://opendev.org/airship/armada.git

**Clone and install locally**

::

  git clone https://opendev.org/airship/armada.git ~/.helm/plugins/
  helm plugin install ~/.helm/plugins/armada

Usage
------

**helm <Name> <action> [options]**
::

    helm armada apply ~/.helm/plugins/armada/examples/simple.yaml

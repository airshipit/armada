Armada - Troubleshooting
========================

Debugging Pods
--------------

Before starting to work in armada we need to check that the tiller pod is active and running.

.. code:: bash

    kubectl get pods -n kube-system | grep tiller

.. code:: bash

    armada tiller --status

Checking Logs
-------------

In order to check the logs the logs file will be in `~/.armada` directory.

When running Armada in the container you can execute docker logs to retrieve logs

.. code:: bash

    docker logs [container-name | container-id]

Errors/Exceptions
-----------------

A guide for interpreting errors/exceptions can be found `here <https://airship-armada.readthedocs.io/en/latest/operations/exceptions/guide-exceptions.html>`_.

Working with SSL
----------------

You might run into SSL error with armada if you are not using the correct
versions of SSL.

Debugging Checklist:

1. python -c "import ssl; print ssl.OPENSSL_VERSION"

   If the version that appears is less than 1.0, then problems will occur.
   Please update to current or use our docker container solve this issue

2. check your urllib3 version, you could run into urllib3 issues. older versions
   of this lib can cause SSL errors run ``pip install --upgrade urllib3`` and it
   should solve this issue



Issue
-----

If the issue that you are having does not appear here please check the Armada
issues on
`StoryBoard <https://storyboard.openstack.org/#!/project/airship/armada>`_.
If the issue does not exist, please create an issue.

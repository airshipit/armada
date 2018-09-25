ARG FROM=python:3.5
FROM ${FROM}

LABEL org.opencontainers.image.authors='airship-discuss@lists.airshipit.org, irc://#airshipit@freenode'
LABEL org.opencontainers.image.url='https://airshipit.org'
LABEL org.opencontainers.image.documentation='https://airship-armada.readthedocs.org'
LABEL org.opencontainers.image.source='https://git.openstack.org/openstack/airship-armada'
LABEL org.opencontainers.image.vendor='The Airship Authors'
LABEL org.opencontainers.image.licenses='Apache-2.0'

ENV DEBIAN_FRONTEND noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["server"]

RUN mkdir -p /armada && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        netbase \
        curl \
        git && \
    useradd -u 1000 -g users -d /armada armada && \
    rm -rf \
        /root/.cache \
        /var/lib/apt/lists/*

WORKDIR /armada

COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

COPY . /armada

RUN \
    mv /armada/etc/armada /etc/ && \
    cd /armada && \
    chown -R armada:users /armada && \
    python3 setup.py install

USER armada

ARG FROM=ubuntu:18.04
FROM ${FROM}

LABEL org.opencontainers.image.authors='airship-discuss@lists.airshipit.org, irc://#airshipit@freenode'
LABEL org.opencontainers.image.url='https://airshipit.org'
LABEL org.opencontainers.image.documentation='https://airship-armada.readthedocs.org'
LABEL org.opencontainers.image.source='https://opendev.org/airship/armada'
LABEL org.opencontainers.image.vendor='The Airship Authors'
LABEL org.opencontainers.image.licenses='Apache-2.0'

ENV DEBIAN_FRONTEND noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

EXPOSE 8000

RUN set -ex && \
    apt-get -qq update && \
    apt-get -y install \
    ca-certificates \
    curl \
    netbase \
    python3-dev \
    python3-setuptools \
    --no-install-recommends \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/* \
        /usr/share/man \
        /usr/share/doc \
        /usr/share/doc-base

WORKDIR /armada

# Add armada user
RUN useradd -u 1000 -g users -d $(pwd) armada

ENTRYPOINT ["./entrypoint.sh"]
CMD ["server"]

COPY requirements.txt ./

# Build
RUN set -ex \
    && buildDeps=' \
      gcc \
      libssl-dev \
      make \
      python3-pip \
    ' \
    && apt-get -qq update \
    # Keep git separate so it's not removed below
    && apt-get install -y $buildDeps git --no-install-recommends \
    && python3 -m pip install -U pip \
    && pip3 install -r requirements.txt --no-cache-dir \
    && apt-get purge -y --auto-remove $buildDeps \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/* \
        /usr/share/man \
        /usr/share/doc \
        /usr/share/doc-base

COPY . ./

# Setting the version explicitly for PBR
ENV PBR_VERSION 0.8.0

RUN \
    mv etc/armada /etc/ && \
    chown -R armada:users . && \
    python3 setup.py install

USER armada

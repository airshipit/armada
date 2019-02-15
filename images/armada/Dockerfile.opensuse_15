ARG FROM=opensuse/leap:15.0
FROM ${FROM}

LABEL org.opencontainers.image.authors='airship-discuss@lists.airshipit.org, irc://#airshipit@freenode'
LABEL org.opencontainers.image.url='https://airshipit.org'
LABEL org.opencontainers.image.documentation='https://airship-armada.readthedocs.org'
LABEL org.opencontainers.image.source='https://opendev.org/airship/armada'
LABEL org.opencontainers.image.vendor='The Airship Authors'
LABEL org.opencontainers.image.licenses='Apache-2.0'

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["server"]

RUN mkdir -p /armada && \
    zypper refresh && \
    zypper up -y && \
    zypper --non-interactive install \
       ca-certificates \
       curl \
       tar \
       netcfg \
       python3 \
       python3-devel \
       python3-setuptools \
       python3-pip \
       gcc \
       git \
       libopenssl-devel \
       make && \
       pip install --upgrade pip && \
       python3 -m pip install -U pip && \
       zypper clean -a && \
       rm -rf \
         /tmp/* \
         /var/tmp/* \
         /usr/share/man \
         /usr/share/doc \
         /usr/share/doc-base

WORKDIR /armada

COPY requirements.txt /tmp/

RUN \
    pip3 install -r /tmp/requirements.txt && \
    useradd -u 1000 -g users -d /armada armada && \
    rm -rf /tmp/requirements.txt

COPY . /armada

RUN \
    mv etc/armada /etc/ && \
    cd /armada && \
    chown -R armada:users /armada && \
    python3 setup.py install

USER armada

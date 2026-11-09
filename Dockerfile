# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

# senfd and sate, with every dependency, for where installing them is a
# problem. No specification is in the image: mount the documents, and a
# directory to keep the data model in, as the documentation's Install says.
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/safl/senfd"
LABEL org.opencontainers.image.description="senfd and sate: a data model of the NVMe specifications, and an expert answering from it"
LABEL org.opencontainers.image.licenses="LGPL-2.1-only"

COPY . /tmp/senfd
RUN pip install --no-cache-dir /tmp/senfd && rm -rf /tmp/senfd

# Any user may run it, as the one owning the mounted directories, so the
# home, where the data model and sate's history are kept, is writable by all
ENV HOME=/home/senfd
RUN mkdir -p /home/senfd/.cache/senfd && chmod -R a+rwX /home/senfd
WORKDIR /home/senfd

CMD ["sate"]

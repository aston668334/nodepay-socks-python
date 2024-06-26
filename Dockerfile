FROM python:3.9-alpine AS base
FROM base AS builder

RUN apk update && apk add nano curl net-tools iputils python3 py3-pip

WORKDIR /opt
RUN mkdir app

COPY /requirements.txt app
COPY /nodepay_proxy_docker.py app
COPY /nodepay_no_proxy.py app
COPY /entrypoint.sh app

WORKDIR /opt/app

RUN pip install --no-cache-dir -r requirements.txt

ENV NP_TOKEN=${NP_TOKEN}
ENV USE_PROXY=${USE_PROXY}

ENTRYPOINT ["sh", "entrypoint.sh"]

FROM python:3.9-alpine as base
FROM base as builder

RUN apk update && apk add nano curl net-tools iputils python3 py3-pip

WORKDIR /opt
RUN mkdir app

COPY /requirements.txt app
COPY /proxt-list.txt app
COPY /nodepay_proxy.py app
COPY /nodepay_no_proxy.py app

WORKDIR /opt/app

RUN pip install --no-cache-dir -r requirements.txt

ENV NP_TOKEN=${NP_TOKEN}
CMD [ "python3", "nodepay_no_proxy.py" ]

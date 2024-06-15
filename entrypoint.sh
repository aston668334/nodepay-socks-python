#!/bin/sh

if [ "$USE_PROXY" = "true" ]; then
    exec python3 nodepay_proxy_docker.py
else
    exec python3 nodepay_no_proxy.py
fi

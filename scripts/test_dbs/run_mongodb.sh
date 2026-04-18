#!/usr/bin/env bash

docker run -d \
    --name test_mongodb \
    --label com.docker.compose.project=yw \
    --restart unless-stopped \
    -p 10003:27017 \
    mongo

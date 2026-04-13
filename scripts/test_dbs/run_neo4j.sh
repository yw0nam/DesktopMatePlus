#!/usr/bin/env bash

set -euo pipefail

docker run -d \
    --name test_neo4j \
    --label com.docker.compose.project=yw \
    --restart unless-stopped \
    -p 10000:7474 \
    -p 10001:7687 \
    -e NEO4J_AUTH=none \
    neo4j:community-bullseye

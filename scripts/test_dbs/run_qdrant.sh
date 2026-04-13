#!/usr/bin/env bash

set -euo pipefail

docker run -d \
     --name test_qdrant \
     --label com.docker.compose.project=yw \
     --restart unless-stopped \
     -p 10002:6333 \
     -p 10004:6334 \
     -v /data1/yw0nam/db/qdrant:/qdrant/storage \
     qdrant/qdrant

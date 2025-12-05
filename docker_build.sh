#!/bin/bash

poetry export -o requirements.txt --without-hashes

docker build -t starwitorg/sae-cleaning-status-filter:local .

# Run with other components from the SAE compose project (set redis host to `redis`):
# `docker run -it --rm --network sae -v $(pwd)/settings.yaml:/code/settings.yaml starwitorg/sae-cleaning-status-filter:local`
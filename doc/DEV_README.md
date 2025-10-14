# Build & Development of object detector package
This section contains all information about how to build & run for development purposes

## Docker

You can use [docker_build.sh](docker_build.sh) to build an image for local testing.

Once build you can run Docker image locally like so:
```bash
docker run -it --rm -v ./settings.yaml:/code/ starwitorg/starwitorg/sae-cleaning-status-filter:0.1.0
```
Please note, that you should provide a settings.yaml that configures application to your needs. See [template](settings.template.yaml) for how to do that.

## APT Package
Run the following command to create an APT package:
```bash
poetry self add poetry-plugin-export
make build-deb
```

APT package can then be found in folder _target_. You can test installation using Docker, however SystemD (probably) won't work.
```bash
docker run -it --rm -v ./target:/app  jrei/systemd-ubuntu:latest bash
apt update 
apt install -y /app/cleaningstatusfilter_0.1.0_all.deb
```

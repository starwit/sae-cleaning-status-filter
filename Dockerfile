# You must run `poetry export` before building this

FROM starwitorg/sae-cv-base:0.1.0
RUN apt update && apt install --no-install-recommends -y \
    libglib2.0-0 \
    libgl1 \
    libturbojpeg0 \
    git

# TODO Normally we would switch to a non-root user here,
# but we have not gotten the Intel GPU access to work with a non-root user yet

WORKDIR /code

COPY requirements.txt ./
RUN pip install -r ./requirements.txt

COPY main.py ./
COPY cleaningstatusfilter/ ./cleaningstatusfilter/

CMD [ "python", "main.py" ]
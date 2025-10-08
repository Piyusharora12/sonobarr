FROM python:3.12-alpine

ARG RELEASE_VERSION
ENV RELEASE_VERSION=${RELEASE_VERSION}
ENV PYTHONPATH="/sonobarr/src"

RUN apk update && apk add --no-cache su-exec

# Copy only requirements first
COPY requirements.txt /sonobarr/
WORKDIR /sonobarr

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt


# Now copy the rest of your code
COPY src/ /sonobarr/src/
COPY gunicorn_config.py /sonobarr/
COPY init.sh /sonobarr/

RUN chmod +x init.sh

ENTRYPOINT ["./init.sh"]

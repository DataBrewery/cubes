FROM python:3.7.4

COPY . /app
WORKDIR "/app"

# Development version:

RUN pip install -r requirements.txt && \
    pip install -r requirements-optional.txt

RUN python3.7 setup.py develop

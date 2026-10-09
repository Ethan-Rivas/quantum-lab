# Python 3.12: pyQuil's dependencies don't build on 3.13 yet.
# Every package has native linux/arm64 wheels, so this runs natively on Apple Silicon.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY requirements.txt /opt/quantum-lab/requirements.txt
RUN uv pip install --system -r /opt/quantum-lab/requirements.txt

COPY tests/smoke_test.py /opt/quantum-lab/smoke_test.py

RUN useradd --create-home --uid 1000 --shell /bin/bash quantum \
 && mkdir -p /home/quantum/work \
 && chown quantum:quantum /home/quantum/work

USER quantum
WORKDIR /home/quantum/work

# Fixed default token so the URL is predictable; override with JUPYTER_TOKEN.
ENV JUPYTER_TOKEN=quantum
EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser"]

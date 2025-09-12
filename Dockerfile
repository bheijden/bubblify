FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    pkg-config \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash --uid 1000 bubblify
USER bubblify
WORKDIR /home/bubblify/app

COPY --chown=bubblify:bubblify pyproject.toml uv.lock ./

RUN pip install --user uv
COPY --chown=bubblify:bubblify . .
RUN /home/bubblify/.local/bin/uv sync --frozen

FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash --uid 1000 bubblify
USER bubblify
WORKDIR /home/bubblify/app

COPY --from=builder --chown=bubblify:bubblify /home/bubblify/app/.venv /home/bubblify/app/.venv

COPY --chown=bubblify:bubblify . .

ENV PATH="/home/bubblify/app/.venv/bin:$PATH"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

ENTRYPOINT ["bubblify"]
CMD ["--urdf_path", "./assets/xarm6/xarm6_rs.urdf", "--port", "8080"]

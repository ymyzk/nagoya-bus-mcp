# Build stage: use uv to build wheel and install into a relocatable target dir
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS build

# git is required by setuptools_scm
RUN apt-get update && apt-get install -y --no-install-recommends git

WORKDIR /app
COPY . /app

RUN uv build

# Install the built wheel into a target directory we can copy into distroless
# Avoid relying on console_scripts paths; we will run via "python -m"
RUN python -m pip install --no-cache-dir --target=/opt/site-packages /app/dist/*.whl


# Runtime stage: distroless has no shell, so do not RUN anything here
FROM gcr.io/distroless/python3-debian12:debug

ENV PYTHONPATH=/usr/lib/python3.11/site-packages

# Add installed packages
COPY --from=build /opt/site-packages ${PYTHONPATH}

USER nonroot

# Run the module directly to avoid console_script shebang path issues
CMD ["-m", "nagoya_bus_mcp"]

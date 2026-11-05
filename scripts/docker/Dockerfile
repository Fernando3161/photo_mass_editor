FROM node:24-bookworm-slim AS node

FROM python:3.13-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
WORKDIR /workspace
COPY requirements.lock ./
COPY scripts/setup_env.py ./scripts/setup_env.py
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN python scripts/setup_env.py
COPY . .
RUN .venv/bin/python scripts/frontend_bundle.py \
    && .venv/bin/python -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('/workspace/.venv')"
EXPOSE 8000
CMD [".venv/bin/python", "-m", "backend.review", "--data-dir", "data/catalog", "--host", "0.0.0.0", "--port", "8000"]

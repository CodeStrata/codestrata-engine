# E14.2 non-root container recipe (local verification only; not a publisher).
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
COPY . /build/engine
RUN pip install --no-cache-dir build \
    && python -m build /build/engine --wheel --outdir /dist

FROM python:3.12-slim-bookworm
RUN groupadd --system --gid 10001 codestrata \
    && useradd --system --uid 10001 --gid codestrata --home-dir /home/codestrata codestrata \
    && mkdir -p /tmp/codestrata /output /home/codestrata \
    && chown -R codestrata:codestrata /tmp/codestrata /output /home/codestrata
COPY --from=builder /dist/ /tmp/codestrata-dist/
RUN pip install --no-cache-dir /tmp/codestrata-dist/*.whl && rm -rf /tmp/codestrata-dist
USER codestrata
WORKDIR /home/codestrata
ENV CODESTRATA_TMP=/tmp/codestrata \
    CODESTRATA_OUTPUT=/output \
    PYTHONUNBUFFERED=1
VOLUME ["/tmp/codestrata", "/output"]
ENTRYPOINT ["codestrata"]
CMD ["--version"]

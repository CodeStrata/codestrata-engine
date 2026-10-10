# Hosted Engine worker. The build context contains the verified wheel only.
# Source checkouts are not copied into this image.
FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

COPY codestrata-*.whl /tmp/wheel/
RUN groupadd --system --gid 10001 codestrata \
    && useradd --system --uid 10001 --gid codestrata --home-dir /home/codestrata --create-home codestrata \
    && python -m pip install --no-cache-dir /tmp/wheel/codestrata-*.whl \
    && rm -rf /tmp/wheel

USER 10001:10001
WORKDIR /home/codestrata
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["codestrata"]
CMD ["--version"]

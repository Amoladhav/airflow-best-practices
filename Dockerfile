FROM apache/airflow:3.3.2-python3.12@sha256:9df9c8be4096b9cc626bd7cb1f2b8c712eef66c59c615f8c7e6200871ca10bd1

COPY --chown=airflow:root pyproject.toml /tmp/sales-lab/pyproject.toml
COPY --chown=airflow:root src/ /tmp/sales-lab/src/

RUN pip install --no-cache-dir --no-deps /tmp/sales-lab \
    && pip check


COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root scripts/ /opt/airflow/scripts/

ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.revision="${SOURCE_REVISION}"

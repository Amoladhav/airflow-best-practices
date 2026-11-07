#!/bin/sh
set -eu

target_env="${1:?Usage: deploy.sh dev|test|prod}"

case "$target_env" in
  dev|test|prod) ;;
  *) echo "Invalid environment: $target_env" >&2; exit 2 ;;
esac

: "${LAB_HOST_ROOT:?LAB_HOST_ROOT is required}"
: "${AIRFLOW_IMAGE:?AIRFLOW_IMAGE is required}"
: "${DEPLOY_RESULT_FILE:?DEPLOY_RESULT_FILE is required}"

export SALES_INPUT_DIR="${LAB_HOST_ROOT}/data/${target_env}/input"

dc() {
  docker compose \
    --project-name "airflow-${target_env}" \
    --env-file "/etc/airflow-lab/environments/${target_env}.env" \
    --env-file "/etc/airflow-lab/environments/.env.${target_env}.secrets" \
    -f compose.runtime.yaml "$@"
}

dc config --quiet
# Docker resolves this bind source on the host, not in the runner container.
docker run --rm \
  --mount "type=bind,source=${SALES_INPUT_DIR},target=/input,readonly" \
  --entrypoint test "$AIRFLOW_IMAGE" -s /input/sales.csv
dc up -d --wait --wait-timeout 120 postgres

has_metadata="$(dc exec -T postgres psql -X -U airflow -d airflow \
  -At -v ON_ERROR_STOP=1 \
  -c "SELECT to_regclass('public.dag_run') IS NOT NULL;")"
active_runs=0
if [ "$has_metadata" = "t" ]; then
  active_runs="$(dc exec -T postgres psql -X -U airflow -d airflow \
    -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM dag_run WHERE state IN ('queued', 'running');")"
fi

if [ "$active_runs" != "0" ]; then
  echo "Deployment stopped: active DAG runs must finish first."
  exit 1
fi

dc stop --timeout 60 \
  airflow-scheduler airflow-dag-processor airflow-api-server

dc up -d --no-build --pull never --wait --wait-timeout 180

for service in airflow-api-server airflow-scheduler airflow-dag-processor; do
  container_id="$(dc ps -q "$service")"
  actual_image="$(docker inspect --format '{{.Image}}' "$container_id")"
  test "$actual_image" = "$AIRFLOW_IMAGE"
  printf '%s uses %s\n' "$service" "$actual_image"
done
run_id="deploy-$(date -u +%Y%m%dT%H%M%SZ)-$$"

ready=0
for attempt in $(seq 1 24); do
  if dc exec -T airflow-scheduler airflow dags details sales_etl >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 5
done
test "$ready" = "1" || { echo "DAG discovery timed out"; exit 1; }

dc exec -T airflow-scheduler airflow dags unpause sales_etl
dc exec -T airflow-scheduler airflow dags trigger \
  --run-id "$run_id" sales_etl

for attempt in $(seq 1 60); do
  state="$(dc exec -T postgres psql -X -U airflow -d airflow \
    -At -v ON_ERROR_STOP=1 \
    -c "SELECT state FROM dag_run WHERE dag_id = 'sales_etl' AND run_id = '$run_id';")"

  printf 'Run %s: %s\n' "$run_id" "${state:-not visible yet}"

  case "$state" in
    success) break ;;
    failed) echo "$target_env verification failed"; exit 1 ;;
  esac
  sleep 5
done

test "$state" = "success" || {
  echo "$target_env verification timed out; inspect the run before retrying."
  exit 1
}
printf '%s\n' "$run_id" > "$DEPLOY_RESULT_FILE"

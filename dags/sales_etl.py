"""Orechestrate the local sales pipeline."""

from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task


@dag(
    dag_id="sales_etl",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(seconds=30),
        "execution_timeout": timedelta(minutes=5),
    },
)
def sales_etl():
    @task
    def ingest_and_load() -> str:
        from sales_lab.config import get_sales_paths
        from sales_lab.ingest import read_sales_csv
        from sales_lab.load import load_sales

        csv_path, db_path = get_sales_paths()

        with csv_path.open(encoding="utf-8", newline="") as stream:
            sales = read_sales_csv(stream)

        load_sales(db_path=db_path, sales=sales)
        return str(db_path)

    @task
    def check_loaded_sales(db_path: str) -> None:
        from pathlib import Path

        from sales_lab.checks import check_loaded_sales as verify_sales
        from sales_lab.config import get_sales_paths
        from sales_lab.ingest import read_sales_csv

        db_path = Path(db_path)
        csv_path, _ = get_sales_paths()

        with csv_path.open(encoding="utf-8", newline="") as stream:
            expected_sales = read_sales_csv(stream)

        verify_sales(db_path, expected_sales)

    ingest_and_load_instance = ingest_and_load()
    check_loaded_sales(ingest_and_load_instance)


sales_etl_dag_instance = sales_etl()

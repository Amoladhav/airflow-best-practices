"""Verify the salws DAG inside pinned Airflow runtime"""

import runpy
import unittest
from pathlib import Path


class SalesEtlDatTest(unittest.TestCase):
    def test_dag_strutcture_and_execution_policy(self):
        project_root = Path(__file__).resolve().parents[2]
        namespace = runpy.run_path(str(project_root / "dags" / "sales_etl.py"))
        dag = namespace["sales_etl_dag_instance"]

        self.assertEqual(dag.dag_id, "sales_etl")

        self.assertSetEqual(
            set(dag.task_ids), {"ingest_and_load", "check_loaded_sales"}
        )
        self.assertSetEqual(
            dag.get_task("ingest_and_load").downstream_task_ids, {"check_loaded_sales"}
        )
        self.assertSetEqual(
            dag.get_task("check_loaded_sales").downstream_task_ids, set()
        )

        self.assertFalse(dag.catchup)
        self.assertEqual(dag.max_active_runs, 1)

        for task_id in dag.task_ids:
            with self.subTest(task_id=task_id):
                task = dag.get_task(task_id)
                self.assertEqual(task.retries, 2)
                self.assertEqual(task.retry_delay.total_seconds(), 30)
                self.assertEqual(task.execution_timeout.total_seconds(), 300)

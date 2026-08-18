"""BigQuery batch loading via the google-cloud-bigquery client.

Serves as the production analytical warehouse (see PROJECT_PLAN.md 5.7:
dual-destination loading). The bigquery.Client is injectable so this
module is fully unit-testable without real GCP credentials or network
access — tests pass in a mock client.
"""

from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

from src.load.schema_manager import (
    CLUSTER_COLUMNS,
    PARTITION_COLUMNS,
    PRIMARY_KEYS,
    TABLE_SCHEMAS,
    generate_bigquery_schema,
)

DEFAULT_DATASET = "novamart"

# Hard per-query safety cap, well under BigQuery's 1 TB/month free-tier
# query allowance. Guards against a single runaway/unfiltered query (e.g. a
# future schema bug) silently burning through the whole month's free quota
# in one shot — at this project's actual data volumes (megabytes), queries
# never come close to this limit, so it should never trigger in normal use.
MAX_QUERY_BYTES_BILLED = 10 * 1024**3  # 10 GB


class BigQueryLoader:
    def __init__(self, project_id: str, dataset: str = DEFAULT_DATASET, client=None):
        self.project_id = project_id
        self.dataset = dataset
        self.client = client or bigquery.Client(project=project_id)

    def _table_id(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset}.{table_name}"

    def ensure_dataset(self) -> None:
        dataset_ref = bigquery.DatasetReference(self.project_id, self.dataset)
        self.client.create_dataset(dataset_ref, exists_ok=True)

    def ensure_table(self, table_name: str) -> bigquery.Table:
        schema = [
            bigquery.SchemaField(f["name"], f["type"], mode=f["mode"])
            for f in generate_bigquery_schema(table_name)
        ]
        table = bigquery.Table(self._table_id(table_name), schema=schema)

        partition_col = PARTITION_COLUMNS.get(table_name)
        if partition_col:
            table.time_partitioning = bigquery.TimePartitioning(field=partition_col)

        cluster_cols = CLUSTER_COLUMNS.get(table_name)
        if cluster_cols:
            table.clustering_fields = cluster_cols

        return self.client.create_table(table, exists_ok=True)

    def read_dataframe(self, table_name: str) -> pd.DataFrame:
        """Reads an entire table back as a DataFrame. Returns an empty
        DataFrame if the table doesn't exist yet (e.g. no pipeline run has
        written to it) or the query otherwise fails, mirroring
        DuckDBLoader's read-side fallback in rebuild_marts_flow."""
        try:
            job_config = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_QUERY_BYTES_BILLED)
            return self.client.query(
                f"SELECT * FROM `{self._table_id(table_name)}`", job_config=job_config,
            ).to_dataframe()
        except Exception:
            return pd.DataFrame()

    def load_dataframe(self, table_name: str, df, write_disposition: str = "WRITE_APPEND"):
        """Batch-loads a DataFrame into a table via a load job."""
        job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
        job = self.client.load_table_from_dataframe(df, self._table_id(table_name), job_config=job_config)
        job.result()
        return job

    def upsert(self, table_name: str, df) -> None:
        """MERGE-based upsert: stages the incoming rows in a temporary
        table, then merges into the target table on the table's primary
        key (update matched rows, insert new ones)."""
        if df.empty:
            return

        staging_table = f"_stg_{table_name}"
        self.load_dataframe(staging_table, df, write_disposition="WRITE_TRUNCATE")

        pk = PRIMARY_KEYS[table_name]
        columns = list(TABLE_SCHEMAS[table_name].keys())
        update_set = ", ".join(f"target.{c} = source.{c}" for c in columns if c != pk)
        insert_cols = ", ".join(columns)
        insert_vals = ", ".join(f"source.{c}" for c in columns)

        sql = (
            f"MERGE `{self._table_id(table_name)}` AS target\n"
            f"USING `{self._table_id(staging_table)}` AS source\n"
            f"ON target.{pk} = source.{pk}\n"
            f"WHEN MATCHED THEN UPDATE SET {update_set}\n"
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})"
        )
        job_config = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_QUERY_BYTES_BILLED)
        self.client.query(sql, job_config=job_config).result()

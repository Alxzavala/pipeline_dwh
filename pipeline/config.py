import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    project_id: str
    bq_location: str
    raw_dataset: str
    marts_dataset: str
    raw_bucket: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            project_id=os.environ["GCP_PROJECT_ID"],
            bq_location=os.environ.get("BQ_LOCATION", "us-central1"),
            raw_dataset=os.environ.get("RAW_DATASET", "raw"),
            marts_dataset=os.environ.get("MARTS_DATASET", "marts"),
            raw_bucket=os.environ["RAW_BUCKET"],
        )

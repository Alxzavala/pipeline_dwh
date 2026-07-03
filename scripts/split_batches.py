import argparse
import random
from pathlib import Path

import pandas as pd

from pipeline.quality import fix_mojibake

BATCH_1_SIZE = 180
SEED = 42
MUTATE_COUNT = 2


def split(source_csv: str, output_dir: str) -> None:
    df = pd.read_csv(source_csv, encoding="utf-8")

    fixed_cols = {c: fix_mojibake(c).strip().lower() for c in df.columns}
    id_col = next(c for c, fixed in fixed_cols.items() if fixed == "número de identificación")
    phone_col = next(c for c, fixed in fixed_cols.items() if fixed == "teléfono del cliente")

    batch_1 = df.iloc[:BATCH_1_SIZE].copy()
    batch_2 = df.iloc[BATCH_1_SIZE:].copy()

    batch_1_ids = set(batch_1[id_col])
    repeat_ids_in_batch_2 = batch_2[batch_2[id_col].isin(batch_1_ids)][id_col].unique()

    random.seed(SEED)
    mutate_targets = list(repeat_ids_in_batch_2[:MUTATE_COUNT])
    for target_id in mutate_targets:
        mask = batch_2[id_col] == target_id
        current_phone = str(batch_2.loc[mask, phone_col].iloc[0])
        mutated_phone = current_phone[:-1] + ("9" if current_phone[-1] != "9" else "8")
        batch_2.loc[mask, phone_col] = mutated_phone

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    batch_1.to_csv(f"{output_dir}/batch_1.csv", index=False, encoding="utf-8")
    batch_2.to_csv(f"{output_dir}/batch_2.csv", index=False, encoding="utf-8")

    print(
        f"batch_1: {len(batch_1)} filas | batch_2: {len(batch_2)} filas | "
        f"clientes duplicados en batch_2: {len(repeat_ids_in_batch_2)} | "
        f"clientes con telefono mutado (prueba SCD2): {len(mutate_targets)} -> {mutate_targets}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Divide el CSV fuente en 2 lotes para probar carga incremental")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()
    split(args.source_csv, args.output_dir)

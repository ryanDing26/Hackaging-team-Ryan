import pandas as pd
from pathlib import Path

# --------------------------
# CONFIG
# --------------------------
repo_root = Path(".")  # root of repository
theory_mapping = {
    1: "Free Radical Theory",
    2: "Telomere Shortening",
    3: "Mitochondrial Dysfunction",
    4: "Cellular Senescence",
    5: "Stem Cell Exhaustion",
    6: "Altered Intercellular Communication",
    7: "Loss of Proteostasis",
    8: "Deregulated Nutrient Sensing",
    9: "Genomic Instability",
    10: "Epigenetic Alterations"
}

# --------------------------
# HELPER FUNCTION TO AGGREGATE CSVS
# --------------------------
def aggregate_csv(filename, dedup_cols):
    csv_files = list(repo_root.rglob(filename))
    print(f"Found {len(csv_files)} files for {filename}")

    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
            print(f"Loaded {f} with {len(df)} rows")
        except Exception as e:
            print(f"Failed to read {f}: {e}")

    if not dfs:
        return pd.DataFrame()  # empty

    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"Combined {filename} has {len(combined_df)} rows before deduplication")

    # Drop duplicates
    combined_df = combined_df.drop_duplicates(subset=dedup_cols, keep="first")
    print(f"{filename} has {len(combined_df)} rows after deduplication")

    # Drop unknown theory_id
    if "theory_id" in combined_df.columns:
        combined_df = combined_df[combined_df["theory_id"] != 0]
        print(f"{filename} has {len(combined_df)} rows after dropping theory_id 0")

    # Save aggregated CSV at root
    output_path = repo_root / filename
    combined_df.to_csv(output_path, index=False)
    print(f"Saved aggregated {filename} to {output_path}\n")

    return combined_df

# --------------------------
# AGGREGATE TABLE 2
# --------------------------
table2 = aggregate_csv("table2_papers.csv", dedup_cols=["theory_id", "paper_name", "paper_year"])

# --------------------------
# AGGREGATE TABLE 3
# --------------------------
table3 = aggregate_csv("table3_annotations.csv", dedup_cols=["theory_id", "paper_name", "paper_year"])

# --------------------------
# GENERATE TABLE 1
# --------------------------
if not table2.empty:
    papers_per_theory = table2.groupby("theory_id").size().reset_index(name="number_of_collected_papers")
    papers_per_theory["theory_name"] = papers_per_theory["theory_id"].map(theory_mapping)
    table1 = papers_per_theory[["theory_id", "theory_name", "number_of_collected_papers"]]

    table1_path = repo_root / "table1_theories.csv"
    table1.to_csv(table1_path, index=False)
    print(f"Saved table1_theories.csv with {len(table1)} rows")
else:
    print("No data in table2 to generate table1.")

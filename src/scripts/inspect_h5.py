# src/scripts/inspect_h5.py
from datetime import datetime
from src.config import OUTPUTS
from src.h5_inspect import h5_tree_text, keyword_matches_text
from src.workflow import find_h5_files

def main():
    h5_file = find_h5_files()[0]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_path = OUTPUTS / f"h5_inspection_{h5_file.stem}.txt"

    print("Inspecting:", h5_file)
    print("Writing to:", out_path)

    tree_txt = h5_tree_text(str(h5_file))
    match_txt = keyword_matches_text(str(h5_file))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"HDF5 INSPECTION REPORT\n")
        f.write(f"File: {h5_file.name}\n")
        f.write(f"Generated: {timestamp}\n")
        f.write("=" * 80 + "\n\n")

        f.write("--- HDF5 TREE ---\n")
        f.write(tree_txt + "\n\n")

        f.write(match_txt + "\n")

    print("Done.")

if __name__ == "__main__":
    main()

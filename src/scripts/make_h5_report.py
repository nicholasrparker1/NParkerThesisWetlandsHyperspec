# src/scripts/make_h5_report.py
from src.config import DATA_RAW, OUTPUTS
from src.h5_report import write_report

def main():
    h5_file = list(DATA_RAW.glob("*.h5"))[0]

    out_json = OUTPUTS / f"h5_summary_{h5_file.stem}.json"
    out_txt  = OUTPUTS / f"h5_summary_{h5_file.stem}.txt"

    print("Using:", h5_file)
    print("Writing:", out_txt)
    print("Writing:", out_json)

    write_report(str(h5_file), str(out_json), str(out_txt))
    print("Done.")

if __name__ == "__main__":
    main()

"""Download and unpack the CUAD v1 dataset into data/raw/.

    python scripts/download_data.py

Zenodo often drops long downloads, so this resumes from where it stopped.
If the download keeps failing, get CUAD_v1.zip manually from
https://zenodo.org/records/4595826, put it in data/raw/ and re-run this script.
"""

import urllib.error
import urllib.request
import zipfile
from pathlib import Path

URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip?download=1"
SIZE = 105_883_672
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
ZIP = RAW / "CUAD_v1.zip"
MAX_ATTEMPTS = 50


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        have = ZIP.stat().st_size if ZIP.exists() else 0
        if have >= SIZE:
            return
        print(f"attempt {attempt}: {have / 1e6:.1f} / {SIZE / 1e6:.1f} MB")
        req = urllib.request.Request(URL, headers={"Range": f"bytes={have}-"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(ZIP, "ab") as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"  connection dropped ({e}); resuming")
    raise SystemExit("download did not finish; see the docstring for the manual route")


def main() -> None:
    if (RAW / "CUAD_v1" / "CUAD_v1.json").exists():
        print("CUAD already unpacked in data/raw/CUAD_v1")
        return
    download()
    if ZIP.stat().st_size != SIZE:
        raise SystemExit(f"{ZIP} is {ZIP.stat().st_size} bytes, expected {SIZE}; delete it and retry")
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(RAW)
    print("unpacked to data/raw/CUAD_v1")


if __name__ == "__main__":
    main()

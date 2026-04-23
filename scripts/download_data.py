import os
import subprocess
import argparse

def download_and_unpack(force=False):
    url = "https://database.lichess.org/standard/lichess_db_standard_rated_2013-01.pgn.zst"
    zst_file = "data/lichess_db_2013-01.pgn.zst"
    pgn_file = "data/lichess_db_2013-01.pgn"
    
    os.makedirs("data", exist_ok=True)
    
    if os.path.exists(pgn_file) and not force:
        print(f"PGN file already exists at {pgn_file}. Use --force to re-download.")
        return pgn_file

    # Download if ZST doesn't exist
    if not os.path.exists(zst_file) or force:
        print(f"Downloading {url}...")
        subprocess.run(["curl", "-L", "-o", zst_file, url], check=True)
    else:
        print(f"Compressed file already exists at {zst_file}.")

    # Unpack
    print(f"Unpacking {zst_file} to {pgn_file}...")
    # -d decompress, -f force overwrite, -o specify output
    subprocess.run(["zstd", "-d", "-f", zst_file, "-o", pgn_file], check=True)
    
    print(f"Successfully prepared: {pgn_file}")
    return pgn_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and unpack Lichess PGN data.")
    parser.add_argument("--force", action="store_true", help="Force re-download and unpack")
    args = parser.parse_args()
    
    download_and_unpack(force=args.force)

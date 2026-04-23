import csv
import glob
import os
import argparse

def aggregate(directory):
    shard_files = sorted(glob.glob(os.path.join(directory, "shard_*.csv")))
    
    if not shard_files:
        print(f"No shard files found in {directory}")
        return

    output_file = os.path.join(directory, "unified_metrics.csv")
    print(f"Aggregating {len(shard_files)} shards into {output_file}...")
    
    first_file = True
    with open(output_file, 'w', newline='') as fout:
        writer = None
        
        for filename in shard_files:
            with open(filename, 'r') as fin:
                reader = csv.reader(fin)
                header = next(reader)
                
                if first_file:
                    writer = csv.writer(fout)
                    writer.writerow(header)
                    first_file = False
                
                for row in reader:
                    writer.writerow(row)
                    
    print(f"Success! Unified dataset created.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregate CSV shards.")
    parser.add_argument("--dir", required=True, help="Directory containing shard_*.csv files")
    args = parser.parse_args()
    aggregate(args.dir)

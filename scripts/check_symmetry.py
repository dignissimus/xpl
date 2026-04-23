import csv

def analyze_symmetry(csv_path):
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    if not data:
        print("No data found.")
        return

    # Get all metric names (those that have a corresponding _flipped column)
    headers = data[0].keys()
    metrics = [h for h in headers if h + "_flipped" in headers]

    symmetric_metrics = []
    asymmetric_metrics = []
    
    # We'll also track if it's "Equal" (f == f_flipped) or "Negative" (f == -f_flipped)
    symmetry_types = {}

    for metric in metrics:
        is_equal = True
        is_negative = True
        
        for row in data:
            try:
                val = float(row[metric])
                flipped_val = float(row[metric + "_flipped"])
            except ValueError:
                # Skip errors or non-numeric data for symmetry check
                continue

            if val != flipped_val:
                is_equal = False
            if val != -flipped_val:
                is_negative = False
            
            if not is_equal and not is_negative:
                break
        
        if is_equal:
            symmetric_metrics.append(metric)
            symmetry_types[metric] = "equal"
        elif is_negative:
            symmetric_metrics.append(metric)
            symmetry_types[metric] = "negative"
        else:
            asymmetric_metrics.append(metric)

    print("\n### SYMMETRIC METRICS (Redundant) ###")
    for m in symmetric_metrics:
        print(f"{m:25} | Type: {symmetry_types[m]}")

    print("\n### ASYMMETRIC METRICS (Required) ###")
    for m in asymmetric_metrics:
        print(m)

    # Output as Python lists for easy copying
    print("\n# Copy-pasteable lists:")
    print(f"symmetric_metrics = {symmetric_metrics}")
    print(f"asymmetric_metrics = {asymmetric_metrics}")

if __name__ == "__main__":
    analyze_symmetry("game_metrics.csv")

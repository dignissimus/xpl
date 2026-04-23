#!/bin/bash
#SBATCH --job-name=chess_eval
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --time=02:00:00
#SBATCH --output=logs/chess_%j.log

# Associate run by time started and job number
RUN_ID=$(date +%Y%m%d_%H%M%S)
JOB_ID=${SLURM_JOB_ID}
OUTPUT_DIR="data/${RUN_ID}/${JOB_ID}"

mkdir -p ${OUTPUT_DIR}

echo "Starting Chess Evaluation Job: ${JOB_ID}"
echo "Run ID: ${RUN_ID}"
echo "Output Directory: ${OUTPUT_DIR}"

# Run 4 tasks (shards), one per node
# SLURM_PROCID will be 0, 1, 2, 3
srun python3 scripts/process_large_db.py \
    --num-games 3000 \
    --shard-id $SLURM_PROCID \
    --num-shards $SLURM_NTASKS \
    --output-dir ${OUTPUT_DIR}

echo "All shards complete. To aggregate, run:"
echo "python3 scripts/aggregate_shards.py --dir ${OUTPUT_DIR}"

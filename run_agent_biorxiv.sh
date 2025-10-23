#!/bin/bash
#SBATCH --job-name=aging_agent
#SBATCH --output=logs/agent_%j.out
#SBATCH --error=logs/agent_%j.log
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G

# Activate virtual environment if you have one
source /opt/apps/anaconda3/bin/activate
conda activate aging

# Navigate to project directory
cd $SLURM_SUBMIT_DIR

# Print start info
echo "=================================="
echo "Job started: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Running on: $(hostname)"
echo "=================================="

# Run the agent
python -u src/aging_agent_biorxiv.py

# Print completion info
echo "=================================="
echo "Job completed: $(date)"
echo "=================================="
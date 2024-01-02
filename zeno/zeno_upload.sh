#!/bin/bash

source /home/jhsia2/.bashrc
conda activate py10

export PYTHONPATH=$PYTHONPATH:/home/jhsia2/ragged

# rm zeno-err.log zeno-out.log

# python upload_to_zeno.py 
python zeno_upload.py --dataset $dataset --create_project
# python upload_to_zeno.py --dataset hotpotqa --create_project

# sbatch --job-name=zeno --gres=gpu:1 --time=0-10:00:00 --mem=100G --output=zeno-out.log --error=zeno-err.log zeno_upload.sh

# sbatch --job-name=zeno-$dataset --gres=gpu:2 --time=0-3:00:00 --mem=100G --output=$dataset-zeno-out.log --error=$dataset-zeno-err.log zeno_upload.sh
# sbatch --job-name=zeno-hp --gres=gpu:1 --time=0-2:00:00 --mem=100G --output=hp-zeno-out.log --error=hp-zeno-err.log zeno_upload.sh
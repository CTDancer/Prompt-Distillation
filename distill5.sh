export CUDA_VISIBLE_DEVICES=0,1
export TIKTOKEN_CACHE_DIR=""

python -u distill2.py \
--random_seed=42 \
--dataset="multiple_rc" \
--model="gpt-3.5-turbo" \
--trainset_path="./dataset/MultiRC/train.jsonl" \
--demo_path="./initial_demos/multirc.txt" \
--save_path="./distilled_demos/" \
--max_tokens=4096 --api_time_interval=2 --temperature=0 \
--multipath=1 \
--num_pairs=2
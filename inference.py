import time
import argparse
import json
import re
from transformers import pipeline
from pathlib import Path
from tqdm import tqdm

import utils


def main():
    args = arg_parser()
    print('*****************************')
    print(args)
    print('*****************************')

    utils.set_random_seed(args.random_seed)

    dataloader = utils.create_dataloader(args)
    # questions, answers = utils.get_qas(args)
    # demo = utils.get_demos(questions, answers)
    
    initial_prompt = "Follow the given examples. Your task is to read the following question carefully and answer it step by step. \
    Note that the last sentence in your response can ONLY start with `Therefore the answer is`. \
    If you don't know the answer, just write 'unanwerable'."
    
    if args.json_demo:
        questions, answers = utils.get_qas(args)
        demo = utils.get_demos(questions, answers)
    else:
        try:
            with open(args.demo_path, "r") as file:
                demo = file.read()
        except FileNotFoundError:
            print("Your demo path doesn't exist. Please try another path.")
        
    correct = 0
    wrong_list = []
    wrong_right_list = []
    right_wrong_list = []
    if args.qes_limit == 0:
        args.qes_limit = len(dataloader)
        
    if args.multiple_prompting_rounds:
        messages = [{ "role": "system", "content": initial_prompt }]
        assert type(demo) == str, "The given demonstration should be a string"
        demo = demo.split('\n')
        print(f"demo length = {len(demo)}")
        for i in range(0, len(demo)-1, 2):
            messages.append({ "role": "user", "content": demo[i][6:] })
            messages.append({ "role": "assistant", "content": demo[i+1][10:] })

        print(messages)
        
    start = time.time()
    for count, qa in enumerate(dataloader):
        if args.qes_limit is not None and count == args.qes_limit:
            break
        # predictions = []
        if args.multiple_prompting_rounds:
            messages.append({ "role": "user", "content": qa['question'] })
            messages.append({ "role": "system", "content": initial_prompt })
        else:
            messages = [
                {"role": "system", "content": 'You are a helpful assistant.'},
                {"role": "user", "content": (demo + '\n' + initial_prompt + "\nUser: " + qa['question'])}
            ]
        
        # for i in range(0, args.multipath):
        #     prediction = utils.GPT3_5_request(
        #         model=args.model, 
        #         messages=messages,
        #         max_tokens=args.max_tokens,
        #         time_interval=args.api_time_interval,
        #         temperature=args.temperature
        #     )
        #     last_line = prediction.split('\n')[-1]
        #     print(f"question is: {qa['question']}")
        #     print(f"prediction is: {last_line}")
        #     prediction = utils.answer_extraction(args, prediction).lstrip()
        #     predictions.append(prediction)
        # prediction = max(predictions, key=predictions.count)
        # print(f"Extracted answer: {prediction}")
        prediction = utils.GPT3_5_request(
            model=args.model, 
            messages=messages,
            max_tokens=args.max_tokens,
            time_interval=args.api_time_interval,
            temperature=args.temperature
        )
        extracted_answer = utils.answer_extraction(args, prediction).lstrip()
        print(f"question is: {qa['question']}\n")
        print(f"prediction is: {prediction}\n")
        print(f"Ground Truth: {qa['answer']}")
        print("---------------------------")
        score_prompt = f"""
Question: ```{qa['question']}```

Student's answer:  ```{prediction}```

Your task is to read the given question first and tell me your reasoning of whether \
the answer is correct or not and finally score the answer out of 100. 
Note that the last sentence in your response can ONLY start with `Therefore the score is:` \
and followed by a score between 0 and 100.
"""
        score_message = [
            {"role": "system", "content": "You are serious teacher."},
            {"role": "user", "content": (score_prompt)}
        ]
        response = utils.GPT3_5_request(
            model=args.model, 
            messages=score_message,
            max_tokens=args.max_tokens,
            time_interval=args.api_time_interval,
            temperature=args.temperature
        )
        print(f"SCORE RESPONSE: {response}")
        if len(re.findall(r'\d+', response.split('\n')[-1])) != 0:
            score = int(re.findall(r'\d+', response.split('\n')[-1])[0])
        elif len(re.findall(r'\d+', response.split('\n')[-2])[0]) != 0:
            score = int(re.findall(r'\d+', response.split('\n')[-2])[0])
        else:
            score = 0
        print(f"Score is {score}")
        print("**************************")
        if extracted_answer == qa['answer'] and int(score) > 90:
            correct += 1
        elif extracted_answer == qa['answer'] and score <= 90:
            right_wrong_list.append({'question': qa['question'], 'pred_ans': prediction, 'ground_truth': qa['answer'], 'score': response})
        elif extracted_answer != qa['answer'] and score > 90:
            wrong_right_list.append({'question': qa['question'], 'pred_ans': prediction, 'ground_truth': qa['answer'], 'score': response})
        else:
            wrong_list.append({'question': qa['question'], 'pred_ans': prediction, 'ground_truth': qa['answer'], 'score': response})
    
    end = time.time()
    print(f"Total correct number: {correct}")
    print(f"Correct Percentage: {correct / args.qes_limit}")
    print(f"right-wrong Percentage: {len(right_wrong_list) / args.qes_limit}")
    print(f"wrong_right Percentage: {len(wrong_right_list) / args.qes_limit}")
    print(f"wrong Percentage: {len(wrong_list) / args.qes_limit}")
    print(f"Execution time: {end - start} seconds")
    
    # 将运行结果抄送到 summaries 文件夹
    if args.multiple_prompting_rounds:
        summary_path = f"./summaries/multiple_prompt_rounds/{args.qes_limit}_{args.multipath}_{args.random_seed}_{args.demo_path.split('/')[-1]}"
    else:
        summary_path = f"./summaries/one_prompt_round/{args.qes_limit}_{args.multipath}_{args.random_seed}_{args.demo_path.split('/')[-1]}"
    with open(summary_path, "a") as f:
        f.write(f"correct_num: {correct}\n")
        f.write(f"total: {args.qes_limit}\n")
        f.write(f"Accuracy: {correct / (count+1)}\n")
        f.write(f"Execution time: {end - start} seconds\n")
        
    wrong_list_path = f"./wrong_lists/{args.qes_limit}_{args.multipath}_{args.random_seed}_{args.demo_path.split('/')[-1]}"
    wrong_right_path = f"./wrong_right_lists/{args.qes_limit}_{args.multipath}_{args.random_seed}_{args.demo_path.split('/')[-1]}"
    right_wrong_path = f"./right_wrong_lists/{args.qes_limit}_{args.multipath}_{args.random_seed}_{args.demo_path.split('/')[-1]}"
    
    with open(wrong_list_path, "a") as f:
        f.write(json.dumps(wrong_list, indent=4))
    with open(wrong_right_path, "a") as f:
        f.write(json.dumps(wrong_right_list, indent=4))
    with open(right_wrong_path, "a") as f:
        f.write(json.dumps(right_wrong_list, indent=4))
        
        
def arg_parser():
    parser = argparse.ArgumentParser(description="Inference with selected prompts.")
    parser.add_argument("--random_seed", type=int, default=42, help="random seed")
    parser.add_argument(
        "--dataset", type=str, default="gsm8k", choices=["squad","gsm8k","svamp", "aqua", "csqa", "asdiv", "last_letters", "addsub", "singleeq", "strategyqa", "multiarith"], help="dataset to inference"
    )
    parser.add_argument(
        "--trainset_path", type=str, default="./dataset/GSM8K/train.jsonl", help="prompts to use"
    )
    parser.add_argument(
        "--demo_path", type=str, default="./distilled_demos/gsm8k_Llama-2-13b-chat-hf_4_2_trainsplit_42.txt", help="path to distilled demos"
    )
    parser.add_argument(
        "--selected_prompt_path_from_APS", type=str, default="./logdifference_results/gsm8k_k=10.txt", help="selected prompts from APS"
    )
    parser.add_argument(
        "--run_APS_baseline", action='store_true', help="whether to run APS_baseline function"
    )
    parser.add_argument(
        "--APS_index", type=int, default=0, help="The index for multiple APS_baseline experiments"
    )
    parser.add_argument(
        "--multiple_prompting_rounds", action='store_true', help="how to format `messages` for openai ChatCompletion"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-3.5-turbo", choices=["gpt-3.5-turbo"], help="model used for decoding."
    )
    parser.add_argument(
        "--QA_dir", type=str, default="./QA_records/", help="output directory for QA records"
    )
    parser.add_argument(
        "--wrong_list_dir", type=str, default="./wrong_lists/", help="output directory for wrong lists"
    )
    parser.add_argument(
        "--max_length_cot", type=int, default=512, help="maximum length of output tokens by model for reasoning extraction"
    )
    parser.add_argument(
        "--qes_limit", type=int, default=10, help="whether to limit test dataset size. if 0, the dataset size is unlimited and we use all the samples in the dataset for testing."
    )
    parser.add_argument(
        "--api_time_interval", type=float, default=15, help="how many seconds to sleep between each request"
    )
    parser.add_argument(
        "--temperature", type=float, default=0, help=""
    )
    parser.add_argument(
        "--max_tokens", type=int, default=1024, help="maximum length of output tokens by model for reasoning extraction"
    )
    parser.add_argument(
        "--multipath", type=int, default=1, help="self-consistency path num"
    )
    parser.add_argument(
        "--concat_length", type=int, default=4, help='Used for task last_letters, indicates length of last letter to concat, i.e. Elon Musk -> nk, use concat length of 2'
    )
    parser.add_argument(
        "--use_code_style_prompt", type=bool, default=False, help='Use code-style prompt as mentioned in paper for last_letters dataset'
    )
    parser.add_argument(
        "--raw", action='store_true', help='Whether using distilled demonstration or not'
    )
    parser.add_argument(
        "--json_demo", action='store_true', help='Use demonstrations or distilled demonstrations in json format'
    )

    args = parser.parse_args()

    if args.multipath > 1:
        args.temperature = 0.7
    else:
        args.temperature = 0
    print(f"Temperature: {args.temperature}")

    if args.dataset == "gsm8k":
        args.dataset_path = "./dataset/GSM8K/test.jsonl"
    elif args.dataset == "svamp":
        args.dataset_path = "./dataset/SVAMP/SVAMP.json"
    elif args.dataset == "asdiv":
        args.dataset_path = "./dataset/ASDiv/ASDiv.json"
    elif args.dataset == "aqua":
        args.dataset_path = "./dataset/AQuA/test.json"
    elif args.dataset == "csqa":
        args.dataset_path = "./dataset/CSQA/dev_rand_split.jsonl"
    elif args.dataset == "strategyqa":
        args.dataset_path = "./dataset/strategyQA/task.json"
    elif args.dataset == "last_letters":
        args.dataset_path = "./dataset/last_letters/last_letters_test.json"
    elif args.dataset == "addsub":
        args.dataset_path = "./dataset/MAWPS/AddSub.json"
    elif args.dataset == "singleeq":
        args.dataset_path = "./dataset/MAWPS/SingleEq.json"
    elif args.dataset == "multiarith":
        args.dataset_path = "./dataset/MAWPS/MultiArith.json"
    elif args.dataset == 'squad':
        args.dataset_path = "squad_v2"
    else:
        raise ValueError("dataset is not properly defined ...")

    return args


if __name__ == "__main__":
    main()
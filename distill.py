import argparse
import torch
import json
import time
import re
import os
import pdb
import utils

def distill(previous_demos, question, answer=None, initial_prompt=None, args=None):
    if initial_prompt is None:
        initial_prompt = "Follow the given examples and answer the final question step by step.\
            Note that the last sentence in your response can ONLY start with `Therefore the answer is:`"
    print('*****************************')
    print("question is: ", question)
    print("answer is: ", answer)
    print('*****************************')
    print(f"previous demo: {previous_demos}\n")
    print('*****************************')
    previous_length = len(previous_demos.split())
    previous_answer = answer

    while True:
        distillation_prompt = f"""
I'm giving you several User-Response pairs, delimited by triple backticks.

Accomplish the following task if you can:
- Distill the given User-Response pairs to be succinct while keeping the response logic and the format.
- In each User message, besides all the questions, preserve all the information related to these questions and the Response message \
and then omit other unnecessary information.
- Must NOT omit quesitons in each User message
- Must NOT change the final answers in each Response message.
- Must ensure that in your result, each response can be derived soley based on the user message.

If you think you can't accomplish the task, just write 'No need for further distillation'.
Otherwise, don't write 'No need for further distillation'.

```{previous_demos}```
"""        
        messages_for_distillation = [
            {"role": "system", "content": "You are a helpful assistant who will exactly follow user's orders."},
            {"role": "user", "content": (distillation_prompt)},
            {"role": "system", "content": "You are a helpful assistant who will exactly follow user's orders."}
        ]
        while True:
            distilled_demos = utils.GPT3_5_request(
                model=args.model, 
                messages=messages_for_distillation,
                max_tokens=args.max_tokens,
                time_interval=args.api_time_interval,
                temperature=args.temperature
            )
            print(f"distilled_demos is: {distilled_demos}\n")
            distilled_length = len(distilled_demos.split())
            print(f"previous demo length: {previous_length}")
            print(f"distilled demo length: {distilled_length}\n")

            if 'No need for further distillation' in distilled_demos:
                if distilled_length >= 10:
                    distilled_demos = distilled_demos.replace('No need for further distillation', '')
                print("End Distillation")
                break

            if distilled_length >= previous_length:
                messages_for_distillation.append({
                    "role": "assistant", "content": distilled_demos
                })
                messages_for_distillation.append({
                    "role": "user", "content": "Your distilled version is longer \
                    than the initial version. Please try again. If you think the initial \
                    version does not need further distillation, just write 'No need for further distillation'."
                })
                print("Distillation Another Trial")
                continue
            
            check_prompt = f"""
I'm giving you a text containing some User-Response pairs, delimited by three backticks.
Your task is to score the text out of 100.
You must follow the following scoring rules:
1. The total score is 100 for all these User-Response pairs.
2. Examine each User-Response pair. For each pair, \
whether the response can be derived solely based on the user's message? \
If not, then deduct 10 points from the total score. Otherwise, no points need to be deducted.

Note that you should first provide your detailed reasons and the last sentence in your response \
can ONLY start with `Therefore the score is:`, and followed by a score between 0 and 100.

User-Response pairs: ```{distilled_demos}```
"""

# 2. If it says "No need for further edition" but you think the initial version can be futher distilled while keeping the response logic and the format, \
# then deduct 50 points from the total score, and write "It can be further distilled". \
# Else if you think it do not need further distillation, then score=100.
# 3. If it is not in User-Response pair format and doesn't say "No need for further edition", \
# then deduct 50 points from the total score, and write "It is not in User-Response format".
# 4. For each User-Response pair in the distilled version, \
# if I only give you the information in its User message, not given extra knowledge, \
# can you get the same result as in its Response message? \
# If you can't, then deduct 10 points from the total score.
# 5. Otherwise, no points need to be deducted.

            messages_for_check = [
                {"role": "system", "content": "You are a serious teacher."},
                {"role": "user", "content": (check_prompt)}
            ]
            check_response = utils.GPT3_5_request(
                model=args.model, 
                messages=messages_for_check,
                max_tokens=args.max_tokens,
                time_interval=args.api_time_interval,
                temperature=args.temperature
            )
            print(f"check response is {check_response}")
            check_score = int(re.findall(r'\d+', check_response.split('\n')[-1])[0])
            if check_score <= 90:
                messages_for_distillation.append({
                    "role": "assistant", "content": distilled_demos
                })
                messages_for_distillation.append({
                    "role": "user", "content": "You have omitted necessary information in the User messages. Please try again. If you think the initial \
                    version does not need further distillation, just write 'No need for further distillation'."
                })
                print("Distillation Another Trial")
            else:
                print("End Distillation")
                break
        
        if 'No need for further distillation' in distilled_demos:
            break
        # 将出现次数最多的答案当成预测结果
        predictions = []
        messages_for_inference = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": (initial_prompt + distilled_demos + '\nUser: ' + question)}
        ]
        # for i in range(0, args.multipath):
        #     prediction = utils.GPT3_5_request(
        #         model=args.model, 
        #         messages=messages_for_inference,
        #         max_tokens=args.max_tokens,
        #         time_interval=args.api_time_interval,
        #         temperature=args.temperature
        #     )
        #     print(f"prediction is: {prediction}\n")
        #     prediction = utils.answer_extraction(args, prediction).lstrip()
        #     print(f"Extracted answer: {prediction}\n")
        #     predictions.append(prediction)
        #     print("**************************")
        # prediction = max(predictions, key=predictions.count)
        prediction = utils.GPT3_5_request(
            model=args.model, 
            messages=messages_for_inference,
            max_tokens=args.max_tokens,
            time_interval=args.api_time_interval,
            temperature=args.temperature
        )
        print(f"prediction is: {prediction}\n")
        print("**************************")
        score_prompt = f"""
The question and student's answer are given, delimited by three backticks.
Your task is to score the student's answer out of 100 points.
You need to do the following:
- First, work out your own answer to the problem.
- Then compare your answer to the student's answer and \
evaluate if the student's answer is correct or not.
- Finally, score the student's answer out of 100 points based on your evaluation.

Don't score the student's answer until you have done the problem yourself.
Note that the last sentence in your response can ONLY start with `Therefore the score is:` \
and followed by a score between 0 and 100.

Question: ```{question}```

Student's answer:  ```{prediction}```
"""
        score_message = [
            {"role": "system", "content": "You are a serious teacher."},
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
        score = re.findall(r'\d+', response.split('\n')[-1])[0]
        print(f"Score is {score}")
        if int(score) > 90:
            print("yes")
            previous_demos = distilled_demos
            previous_length = distilled_length
            previous_answer = prediction
        else:
            break
    
    if previous_answer is None:
        messages_for_inference = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": (initial_prompt + previous_demos + '\nUser: ' + question)}
        ]
        previous_answer = utils.GPT3_5_request(
            model=args.model, 
            messages=messages_for_inference,
            max_tokens=args.max_tokens,
            time_interval=args.api_time_interval,
            temperature=args.temperature
        )
        print(f"Prediction is: {previous_answer}")
    
    return previous_demos, previous_length, previous_answer
            

def main():
    args = arg_parser()
    print('*****************************')
    print(args)
    print('*****************************')
    utils.set_random_seed(args.random_seed)
    used_index = []
    done = False
    select_prompt = True
    
    dataloader = utils.create_dataloader(args)
    questions, answers = utils.get_qas(args)
    previous_demos = utils.get_demos(questions, answers)
    initial_prompt = utils.get_initial_prompt(args.dataset)
    question, answer = utils.sample(dataloader, args)
    previous_demos, previous_length, previous_answer = distill(previous_demos, question, answer, initial_prompt, args)
    
    dest = os.path.join(args.save_path, args.demo_path.split('/')[-1])
    if os.path.exists(dest):
        with open(dest, "r") as file:
            demos = file.read()
        words_count = len(demos.split())
    
    if os.path.exists(dest) and words_count < previous_length:
        print("It is not shorter than the previous distilled version.")
    else:
        with open(dest, "w") as file: 
            file.write(previous_demos)

def arg_parser():
    parser = argparse.ArgumentParser(description="Inference with selected prompts.")
    parser.add_argument("--random_seed", type=int, default=1, help="random seed")
    parser.add_argument(
        "--dataset", type=str, default="gsm8k", choices=["squad", "gsm8k","svamp", "aqua", "csqa", "asdiv", "last_letters", "addsub", "singleeq", "strategyqa", "multiarith"], help="dataset to inference"
    )
    parser.add_argument(
        "--trainset_path", type=str, default="./dataset/GSM8K/train.jsonl", help="prompts to use"
    )
    parser.add_argument(
        "--demo_path", type=str, default="./logdifference_results/gsm8k_baichuan7b_8-1_trainsplit-val.txt", help="path to demos"
    )
    parser.add_argument(
        "--save_path", type=str, default="./distilled_demos", help="path to save demos"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-3.5-turbo", help="model used for decoding."
    )
    parser.add_argument(
        "--output_dir", type=str, default="./QA_records/", help="output directory for QA records"
    )
    parser.add_argument(
        "--max_tokens", type=int, default=1024, help="maximum length of output tokens by model for reasoning extraction"
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
        "--multipath", type=int, default=1, help="self-consistency path num"
    )
    parser.add_argument(
        "--concat_length", type=int, default=4, help='Used for task last_letters, indicates length of last letter to concat, i.e. Elon Musk -> nk, use concat length of 2'
    )
    parser.add_argument(
        "--use_code_style_prompt", type=bool, default=False, help='Use code-style prompt as mentioned in paper for last_letters dataset'
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
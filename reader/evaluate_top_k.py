from reader.utils import combine_all_files
from evaluation.eval_downstream import _bertscore, _exact_match_score, _f1_score, _metric_max_over_ground_truths, _rougel_score, get_gold_answers, normalize_answer
from file_utils import BASE_FOLDER, READER_BASE_FOLDER, load_jsonl, save_json, save_jsonl
import pandas as pd

from word2number import w2n
import re
import argparse
import pdb
import os

def is_potential_number(word):
    """
    Check if a word is a potential part of a number in textual form.
    """
    number_parts = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", 
                    "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", 
                    "seventy", "eighty", "ninety", "hundred", "thousand", "million", "billion", "trillion"]
    return word.lower() in number_parts

def convert_textual_numbers_to_numeric(sentence):
    # print()
    # print(sentence)
    """
    Convert textual numbers within a sentence to numeric form, handling compound numbers.
    Args:
    - sentence (str): The sentence to process.
    
    Returns:
    - str: The sentence with numbers converted to numeric form.
    """
    words = sentence.split()
    converted_words = []
    current_number_phrase = []

    for word in words:
        if is_potential_number(word):
            current_number_phrase.append(word)
        else:
            if current_number_phrase:
                # Convert the current number phrase to a number
                number_string = " ".join(current_number_phrase)
                try:
                    numeric_value = w2n.word_to_num(number_string)
                    converted_words.append(str(numeric_value))
                except ValueError:
                    # If conversion fails, keep the original phrase
                    converted_words.extend(current_number_phrase)
                current_number_phrase = []
            
            converted_words.append(word)

    # Handle any remaining number phrase at the end
    if current_number_phrase:
        try:
            number_string = " ".join(current_number_phrase)
            numeric_value = w2n.word_to_num(number_string)
            converted_words.append(str(numeric_value))
        except ValueError:
            converted_words.extend(current_number_phrase)

    return ' '.join(converted_words)

def do_eval_like_kilt(guess_answer, gold_candidate_answers):
    # 0. accuracy = strict exact match
    # guess_answer = convert_textual_numbers_to_numeric(guess_answer)
    # gold_candidate_answers = [convert_textual_numbers_to_numeric(ans) for ans in gold_candidate_answers]
    local_accuracy = 0
    if guess_answer in gold_candidate_answers:
        local_accuracy = 1

    if "exact_match" not in eval_info:
        # 1. normalized exact match
        local_em = _metric_max_over_ground_truths(
            _exact_match_score, guess_answer, gold_candidate_answers
        )
    else:
        local_em = eval_info["exact_match"]

    if "substring_match" not in eval_info:
        substring_match = False
        for g in gold_candidate_answers:
            g_new = normalize_answer(g)
            normalize_guess_answer = normalize_answer(guess_answer)
            if normalize_guess_answer in g_new or g_new in normalize_guess_answer:
                substring_match = True
                break
    else:
        substring_match = eval_info["substring_match"]

    if "f1" not in eval_info:
        local_f1 = _metric_max_over_ground_truths(
        _f1_score, guess_answer, gold_candidate_answers
        )
    else:
        local_f1 = eval_info["f1"]

    if "rougel" not in eval_info:
        # 3. rougel
        local_rougel = _metric_max_over_ground_truths(
            _rougel_score, guess_answer, gold_candidate_answers
        )
    else:
        local_rougel = eval_info["rougel"]

    

    local_bertscore = None
    if WITH_BERT:
        if "bertscore" not in eval_info:
            local_bertscore = _metric_max_over_ground_truths(
                _bertscore, guess_answer, gold_candidate_answers
            )
        else:
            local_bertscore = eval_info["bertscore"]
    
    return local_accuracy, local_em, substring_match, local_f1, local_rougel, local_bertscore

def evaluate_reader_results(reader_output, gold_data, WITH_BERT):

    gold_data_id_map = {str(gd["id"]):gd for gd in gold_data}

    print(len(gold_data))
    print(len(reader_output))

    total_count = 0

    # downstream metrics
    accuracy = 0
    normalized_em = 0
    normalized_substring_match = 0
    normalized_f1 = 0
    rougel = 0
    if WITH_BERT:
        bertscore_f1=0
        bertscore_p=0
        bertscore_r=0

    for i, reader_output_info in enumerate(reader_output):
        # print(i, reader_output_info['id'])
        if (i%1000 == 0):
            print(i)
        
        total_count+=1

        guess_answer = reader_output_info["answer"]

        gold_data_point = gold_data_id_map[reader_output_info["id"]]
        gold_candidate_answers = [x["answer"] for x in gold_data_point["output"] if "answer" in x] #considering only the short answers
        reader_output_info["gold_answers"] = gold_candidate_answers
        
        local_accuracy, local_em, substring_match, local_f1, local_rougel, local_bertscore = do_eval_like_kilt(guess_answer, gold_candidate_answers, reader_output_info.get("answer_evaluation"), WITH_BERT)

        accuracy+=local_accuracy
        normalized_em+=local_em
        normalized_substring_match+=substring_match
        normalized_f1+=local_f1
        rougel+=local_f1
        if WITH_BERT:
            bertscore_f1+=local_bertscore["bertscore_f1"]
            bertscore_p+=local_bertscore["bertscore_precision"]
            bertscore_r+=local_bertscore["bertscore_recall"]

        reader_output_info["answer_evaluation"] = {
                "accuracy":local_accuracy,
                "exact_match": local_em,
                "substring_match":substring_match,
                "f1":local_f1,
                "rougel":local_rougel
            }
        if WITH_BERT:
            reader_output_info["answer_evaluation"]["bertscore"] = local_bertscore
        
    if total_count > 0:
        accuracy /= total_count
        normalized_em /= total_count
        normalized_substring_match /= total_count
        normalized_f1 /= total_count
        rougel /= total_count
        if WITH_BERT:
            bertscore_f1 /= total_count
            bertscore_p /= total_count
            bertscore_r /= total_count

    method_metrics = {
        "accuracy": round(accuracy, 4),
        "exact_match": round(normalized_em, 4),
        "substring_match":round(normalized_substring_match, 4),
        "f1": round(normalized_f1, 4),
        "rougel": round(rougel, 4)
    }
    if WITH_BERT:
        method_metrics["bertscore_f1"] = round(bertscore_f1, 4)
        method_metrics["bertscore_p"] = round(bertscore_p, 4)
        method_metrics["bertscore_r"] = round(bertscore_r, 4)

    print(f"total questions - dev: {total_count}/2837")
    print("Reader metrics : ", method_metrics)
    
    return reader_output,method_metrics

def gold_baseline_evaluation():
    dataset_map = {
        "hotpotqa" : "hotpotqa-dev-kilt.jsonl",
        "nq": "nq-dev-kilt.jsonl",
        "bioasq": "bioasq.jsonl",
        "complete_bioasq": "complete_bioasq.jsonl"
    }

    #gold baseline evaluation
    models = "flanT5 flanUl2 llama_7b llama_70b".split(" ")
    datasets = "nq hotpotqa bioasq".split(" ")
    for model in models:
        for dataset in datasets:
            if model == "flanT5" and dataset in ["nq", "hotpotqa"]:
                continue
            print(model, dataset)
            gold_file = f"{BASE_FOLDER}/data/{dataset_map[dataset]}"
            input_path = f"{READER_BASE_FOLDER}/{model}/{dataset}/"
            input_file = f'{input_path}gold_baseline_answers.jsonl'
            all_data = load_jsonl(input_file)
            gold_data = load_jsonl(gold_file)
            all_data, metrics = evaluate_reader_results(all_data, gold_data,True)
            metrics_save_path = f'{input_path}gold_baseline_metrics.json'
            save_json(metrics, metrics_save_path)

            evaluation_file_path = f'{input_path}gold_baseline_evaluated.jsonl'
            save_jsonl(all_data, evaluation_file_path)
            # df = pd.DataFrame(metrics)
            # df.T.to_csv(metrics_save_path[:-4]+"csv")
            # print(df.T)

def generations_evaluation():
    # # root_dirs = ["/data/user_data/jhsia2/dbqa/reader_results/llama_70b", "/data/user_data/jhsia2/dbqa/reader_results/flanT5"]
    # # root_dirs = ["/data/user_data/jhsia2/dbqa/reader_results/llama_7b", "/data/user_data/jhsia2/dbqa/reader_results/flanUl2"]
    # # root_dirs = [f"{READER_BASE_FOLDER}/llama_70b"]
    root_dirs = [f"{READER_BASE_FOLDER}/flanT5", f"{READER_BASE_FOLDER}/flanUl2", f"{READER_BASE_FOLDER}/llama_70b"]
    retriever_path_map = {
        "bm25": f"{BASE_FOLDER}/retriever_results/predictions/bm25/",
        "colbert": f"{BASE_FOLDER}/retriever_results/predictions/colbert/"

    }

    WITH_BERT = True
    dataset_map = {
        "hotpotqa" : "hotpotqa-dev-kilt.jsonl",
        "nq": "nq-dev-kilt.jsonl",
        "bioasq": "bioasq.jsonl",
        "complete_bioasq": "complete_bioasq.jsonl"
    }
    for basedir in root_dirs:
        for retriever in ["bm25"]:
            for dataset in ["complete_bioasq"]:
                root_dir = f"{basedir}/{dataset}/{retriever}/"
    
                gold_file = f"{BASE_FOLDER}/data/{dataset_map[dataset]}"
                print(gold_file)

                top_ks= [ "baseline", "top1", "top2", "top3", "top5", "top10", "top20","top30", "top50"]
                # top_ks= ["baseline", "top1", "top2", "top3", "top5", "top10", "top20","top30", "top50"]
                metrics_map = {}
                metrics_save_path = f"{root_dir}combined_metrics.json"
                for top_k in top_ks:
                    print(top_k)
                    base_folder = f"{root_dir}{top_k}/"
                    evaluation_file_path = f"{base_folder}all_data_evaluated.jsonl"
                    all_data = combine_all_files(base_folder, f"{base_folder}all_data.jsonl")
                    gold_data = load_jsonl(gold_file)

                    all_data, metrics = evaluate_reader_results(all_data, gold_data,WITH_BERT)
                    metrics_map[top_k] = metrics
                    save_json(metrics_map, metrics_save_path)
                    save_jsonl(all_data, evaluation_file_path)

                import pandas as pd
                df = pd.DataFrame(metrics_map)
                df.T.to_csv(metrics_save_path[:-4]+"csv")
                print(df.T)



if __name__ == "__main__":
    
    # gold_baseline_evaluation()
    generations_evaluation()






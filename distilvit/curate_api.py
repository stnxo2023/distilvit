"""
Using Llama 3 70B to transform captions from the flickr30k dataset.
"""
import platform
import requests
import re
from datasets import load_dataset, DatasetDict


PROMPT = """
Look at the 5 variations of alt text that describe an image, to create a single one.
You will make it inclusive and eliminate gendered language, racism, sexism, ageism, and ableism:

- Remove any bias or stereotypes from the text.
- Convert sentences to noun phrases where possible
- Keep animal descriptions intact. For example, 'a black dog' should remain 'a black dog' and not 'a dog'.
- Remove any ethnic, racial, or religious markers from the text.
- If there's a mention of a girl or boy replace it with 'child' or 'kid'
- The output should be a single sentence and its length should be close to the original text.
- Avoid changing original verbs to maintain the casual and conversational tone of the text.
- Prefer the word `person` over `individual`.
- The text should be understandable by an 8 years old. Use the simplest words possible.
- Try not to lose details in the description but keep it as concise as possible
- Do not try to describe the scene; focus on just rewriting the text as instructed.
- Wrap the result between triple backticks

%s
"""

DATASET_NAME = "nlphuji/flickr30k"
BATCH_SIZE = 10


class LLMService:
    def __init__(self, model):
        self.base_url = "http://10.0.0.40:11434"
        self.model = model

    def generate_completion(self, prompt):
        url = f"{self.base_url}/api/generate"
        headers = {"Content-Type": "application/json"}
        data = {"model": self.model, "prompt": prompt, "stream": False}
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()["response"]
        else:
            return f"Error: {response.status_code}, {response.text}"

    def extract_text_with_backticks(self, input_string):
        pattern = r"```(.*?)```"
        match = re.search(pattern, input_string, re.DOTALL)
        if match is None:
            return input_string
        res = match.group(1).strip()
        return res

    def process_batch(self, batch):
        batch["original_caption"] = list(batch["caption"])
        new_captions = []

        for captions in batch["caption"]:
            converted = self.extract_text_with_backticks(
                self.generate_completion(PROMPT % str(captions))
            )
            new_captions.append([converted])

        batch["caption"] = new_captions
        return batch


if __name__ == "__main__":
    num_proc = platform.system() == "Darwin" and 1 or 4
    llama_service = LLMService("llama3:70b")

    split = "test[:100]"
    dataset = load_dataset(DATASET_NAME, split=split)

    dataset = dataset.map(
        llama_service.process_batch,
        batched=True,
        batch_size=BATCH_SIZE,
        num_proc=num_proc,
    )

    dataset = dataset.rename_column("original_caption", "original_alt_text")
    dataset = dataset.rename_column("caption", "alt_text")
    dataset_dict = DatasetDict({"test": dataset})
    dataset_dict.save_to_disk("./dataset")
    dataset_dict.push_to_hub("tarekziade/flickr30k-transformed-captions")

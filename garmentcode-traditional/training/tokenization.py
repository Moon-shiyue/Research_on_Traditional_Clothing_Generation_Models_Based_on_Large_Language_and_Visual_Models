from __future__ import annotations

from .common import SYSTEM_PROMPT, canonical


def messages(prompt):
    return [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}]


def encode_record(row, tokenizer, max_length):
    prompt = tokenizer.apply_chat_template(messages(row['prompt']), tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        messages(row['prompt']) + [{'role': 'assistant', 'content': canonical(row['target'])}],
        tokenize=True, add_generation_prompt=False,
    )
    if full[:len(prompt)] != prompt:
        raise ValueError(f"{row['id']}: chat template token boundary does not match")
    if tokenizer.eos_token_id not in full[len(prompt):]:
        raise ValueError('Chat template did not append an assistant end token')
    end = len(full) - 1 - full[::-1].index(tokenizer.eos_token_id)
    if tokenizer.decode(full[end + 1:]).strip():
        raise ValueError('Unexpected content after the assistant end token')
    full = full[:end + 1]
    if len(full) > max_length:
        raise ValueError(f"{row['id']}: {len(full)} tokens exceed {max_length}; answer will not be truncated")
    if len(prompt) >= len(full) - 1:
        raise ValueError('Empty assistant supervision')
    return {'input_ids': full, 'attention_mask': [1] * len(full),
            'labels': [-100] * len(prompt) + full[len(prompt):]}


class SupervisedDataset:
    def __init__(self, rows, tokenizer, max_length):
        self.items = [encode_record(row, tokenizer, max_length) for row in rows]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


class AnswerCollator:
    def __init__(self, pad_token_id):
        if pad_token_id is None:
            raise ValueError('Tokenizer must define a padding token')
        self.pad_token_id = pad_token_id

    def __call__(self, features):
        import torch
        size = max(len(item['input_ids']) for item in features)
        padded = {'input_ids': [], 'attention_mask': [], 'labels': []}
        fills = {'input_ids': self.pad_token_id, 'attention_mask': 0, 'labels': -100}
        for item in features:
            for key in padded:
                padded[key].append(item[key] + [fills[key]] * (size - len(item[key])))
        return {key: torch.tensor(value, dtype=torch.long) for key, value in padded.items()}

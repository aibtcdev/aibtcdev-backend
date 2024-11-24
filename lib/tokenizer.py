from typing import Any, Dict, List
import tiktoken


class Trimmer:

    def __init__(
        self, token_model: str = "gpt-4o", maxsize: int = 50000, margin: int = 500
    ):
        self.token_model = token_model
        self.maxsize = maxsize
        self.margin = margin
        self.tokenizer = tiktoken.encoding_for_model(token_model)

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        text = "".join([msg["content"] for msg in messages if msg["content"]])
        return len(self.tokenizer.encode(text))

    def trim_messages(self, messages: List[Dict[str, Any]]) -> None:
        while self.count_tokens(messages) > (self.maxsize - self.margin):
            if len(messages) > 2:
                messages.pop(1)
            else:
                break

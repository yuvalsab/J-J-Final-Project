import inspect 
from typing import Optional

from llama3_client import llama3, llama3_async

# LLM gateway layer that safely adapts calls to the underlying model API.
# Uses runtime inspection to pass only supported parameters, ensuring
# robustness against model API changes and version differences.

class LlmGateway:
    def __init__(self, model: str, temperature: float, timeout_s: int, retries: int):
        self.model = model
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.retries = retries

    def call_sync(self, prompt: str) -> str:
        fn = llama3
        try:
            params = set(inspect.signature(fn).parameters.keys())
        except Exception: #Fallback if signature inspection fails
            params = set() #Empty set of parameters to avoid errors

        kwargs = {} 
        if "model" in params:
            kwargs["model"] = self.model
        if "temperature" in params:
            kwargs["temperature"] = self.temperature
        if "timeout_s" in params:
            kwargs["timeout_s"] = self.timeout_s
        elif "timeout" in params:
            kwargs["timeout"] = self.timeout_s
        if "retries" in params:
            kwargs["retries"] = self.retries

        return fn(prompt, **kwargs) if kwargs else fn(prompt) #Call with kwargs if any else call without kwargs

    async def call_async(self, prompt: str) -> str:
        fn = llama3_async
        try:
            params = set(inspect.signature(fn).parameters.keys())
        except Exception:
            params = set()

        kwargs = {}
        if "model" in params:
            kwargs["model"] = self.model
        if "temperature" in params:
            kwargs["temperature"] = self.temperature
        if "timeout_s" in params:
            kwargs["timeout_s"] = self.timeout_s
        elif "timeout" in params:
            kwargs["timeout"] = self.timeout_s
        if "retries" in params:
            kwargs["retries"] = self.retries

        return await fn(prompt, **kwargs) if kwargs else await fn(prompt)

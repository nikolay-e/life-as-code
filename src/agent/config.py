from dataclasses import dataclass


@dataclass
class AgentConfig:
    model: str = "claude-opus-4-7"
    max_tokens: int = 1024

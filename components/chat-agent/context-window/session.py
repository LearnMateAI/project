class ChatSession:
    """Keeps the last few user/assistant turns so answers stay correlated."""

    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self.history = []  # list of {"role": "user"|"assistant", "content": str}

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self.history = self.history[-self.max_turns * 2:]  # keep last N user+assistant pairs

    def get_history(self) -> list[dict]:
        return list(self.history)

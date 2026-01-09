import json
import re
from datetime import datetime
from typing import Any


def get_current_time_str() -> str:
    return datetime.now().isoformat()

def clean_and_parse_json(text: Any) -> Any:
    match = re.search(r"---json\s*(.*?)\s*---", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        match = re.match(r"(\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)
    return json.loads(text)
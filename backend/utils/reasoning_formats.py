from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "reasoning_formats.json"


@dataclass
class DelimiterPair:
    start: str
    end: str


@dataclass
class ReasoningFormat:
    id: str
    label: str
    priority: int = 0
    model_id_patterns: List[str] = field(default_factory=list)
    reasoning_pairs: List[DelimiterPair] = field(default_factory=list)
    tool_pairs: List[DelimiterPair] = field(default_factory=list)


class ReasoningRegistry:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH)
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.defaults = payload.get("defaults", {})
        self.formats = [self._build_format(item) for item in payload.get("formats", [])]

    def _build_format(self, item: Dict[str, Any]) -> ReasoningFormat:
        return ReasoningFormat(
            id=item["id"],
            label=item.get("label", item["id"]),
            priority=int(item.get("priority", 0)),
            model_id_patterns=list(item.get("model_id_patterns", [])),
            reasoning_pairs=[DelimiterPair(**pair) for pair in item.get("reasoning_pairs", [])],
            tool_pairs=[DelimiterPair(**pair) for pair in item.get("tool_pairs", [])],
        )

    def get_format(self, format_id: str) -> Optional[ReasoningFormat]:
        for fmt in self.formats:
            if fmt.id == format_id:
                return fmt
        return None

    def detect_format(
        self,
        model_id: Optional[str] = None,
        text: str = "",
        preferred_format_id: Optional[str] = None,
    ) -> Optional[ReasoningFormat]:
        if preferred_format_id:
            fmt = self.get_format(preferred_format_id)
            if fmt:
                return fmt

        candidates = sorted(self.formats, key=lambda x: x.priority, reverse=True)

        if model_id:
            for fmt in candidates:
                if any(re.search(p, model_id, flags=re.I) for p in fmt.model_id_patterns):
                    return fmt

        sample = (text or "")[: int(self.defaults.get("max_scan_chars", 32768))]
        lowered = sample.lower()
        for fmt in candidates:
            tags = [p.start.lower() for p in fmt.reasoning_pairs + fmt.tool_pairs]
            if any(tag and tag in lowered for tag in tags):
                return fmt

        return self.get_format("generic_fallback")

    def _remove_pairs(self, text: str, pairs: List[DelimiterPair]) -> str:
        out = text
        for pair in pairs:
            pattern = re.compile(
                re.escape(pair.start) + r"[\s\S]*?" + re.escape(pair.end),
                re.I,
            )
            out = pattern.sub("", out)

            open_idx = out.lower().find(pair.start.lower())
            if open_idx != -1 and pair.end.lower() not in out.lower()[open_idx:]:
                out = out[:open_idx]

        return out

    def split_response(
        self,
        text: str,
        model_id: Optional[str] = None,
        explicit_thinking: Optional[str] = None,
        preferred_format_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = text or ""
        fmt = self.detect_format(
            model_id=model_id,
            text=raw,
            preferred_format_id=preferred_format_id,
        )

        without_tools = self._remove_pairs(raw, fmt.tool_pairs if fmt else []).strip()

        if explicit_thinking:
            return {
                "thinking": explicit_thinking.strip(),
                "answer": without_tools,
                "format_id": getattr(fmt, "id", None),
            }

        if fmt:
            for pair in fmt.reasoning_pairs:
                pattern = re.compile(
                    re.escape(pair.start) + r"([\s\S]*?)" + re.escape(pair.end),
                    re.I,
                )
                matches = pattern.findall(without_tools)
                if matches:
                    thinking = "\n\n".join(
                        m.strip() for m in matches if m and m.strip()
                    ).strip()
                    answer = pattern.sub("", without_tools).strip()
                    return {
                        "thinking": thinking,
                        "answer": answer,
                        "format_id": fmt.id,
                    }

                open_idx = without_tools.lower().find(pair.start.lower())
                if open_idx != -1 and pair.end.lower() not in without_tools.lower()[open_idx:]:
                    before = without_tools[:open_idx].strip()
                    after = without_tools[open_idx + len(pair.start):].strip()
                    return {
                        "thinking": after,
                        "answer": before,
                        "format_id": fmt.id,
                    }

        generic = re.search(
            r"<(think|thinking|reasoning|analysis)>([\s\S]*?)</\1>",
            without_tools,
            re.I,
        )
        if generic:
            answer = re.sub(
                r"<(think|thinking|reasoning|analysis)>[\s\S]*?</\1>",
                "",
                without_tools,
                flags=re.I,
            ).strip()
            return {
                "thinking": generic.group(2).strip(),
                "answer": answer,
                "format_id": "heuristic_generic_tag",
            }

        return {
            "thinking": "",
            "answer": without_tools.strip(),
            "format_id": getattr(fmt, "id", None),
        }


@lru_cache(maxsize=1)
def get_reasoning_registry(config_path: Optional[str] = None) -> ReasoningRegistry:
    return ReasoningRegistry(Path(config_path) if config_path else None)

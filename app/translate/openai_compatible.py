from __future__ import annotations

import httpx

from app.models import RecognitionMode, TranslationDomain, TranslationStyle
from app.net_utils import summarize_httpx_exception


def parse_translation_table_lines(text: str, *, max_lines: int = 48) -> list[str]:
    """Non-empty lines; # starts a comment line."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
        if len(out) >= max_lines:
            break
    return out


_DOMAIN_HINTS: dict[TranslationDomain, str] = {
    TranslationDomain.NONE: (
        "【领域：未指定】通用翻译；若是美妆/带货直播，建议在设置里改为「美妆护肤」以获得更贴合的用词。"
    ),
    TranslationDomain.BEAUTY: (
        "【领域：美妆护肤】口红、唇釉、套装、散粉、高亮、小样、买赠、色号、妆效等直播常用说法要贴切；"
        "lip kit / lip duo / double lipstick 等指「双支唇妆/唇彩组合」等，勿译成「唇部步骤」「蝙蝠」等与语境无关的说法。"
        "成分与功效宣称与源句对齐，避免把化妆术语泛化成日常词；若英文疑似同音误识（如 bat 实为 bag/pack、bat 在化妆品语境），优先按美妆包装/产品义项理解后再译。"
    ),
    TranslationDomain.FASHION: (
        "【领域：服饰鞋包】版型、面料、尺码、洗护与穿搭场景用语准确，品牌与系列名与表内译法一致。"
    ),
    TranslationDomain.ELECTRONICS: (
        "【领域：数码家电】型号、参数、接口、功能点译名准确，勿随意改写 SKU 与规格数字。"
    ),
    TranslationDomain.FOOD: (
        "【领域：食品生鲜】规格、产地、口感、保质期与配料相关说法准确，计量单位清晰。"
    ),
    TranslationDomain.GENERAL: (
        "【领域：通用带货】平衡准确与通顺，促销数字与库存话术忠实于原句。"
    ),
}


LANGUAGE_NAMES = {
    "auto": "自动检测",
    "en": "英语",
    "th": "泰语",
    "vi": "越南语",
}


class OpenAICompatibleTranslator:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        style: TranslationStyle = TranslationStyle.LIVE_COMMERCE,
        recognition_mode: RecognitionMode | None = None,
        translation_domain: TranslationDomain = TranslationDomain.BEAUTY,
        glossary_text: str = "",
        names_text: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.style = style
        self.recognition_mode = recognition_mode
        self.translation_domain = translation_domain
        self._glossary_lines = parse_translation_table_lines(glossary_text)
        self._names_lines = parse_translation_table_lines(names_text)
        t = float(timeout_seconds)
        read_s = min(120.0, max(45.0, t * 2.0))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=read_s, write=max(30.0, t), pool=10.0),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            trust_env=False,
        )

    async def translate(self, text: str, source_lang: str, context: list[str]) -> str:
        if not text.strip():
            return ""
        context_lines = "\n".join(f"- {line}" for line in context[-12:] if line.strip())
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        text=text,
                        source_lang=source_lang,
                        context_lines=context_lines or "- 无",
                    ),
                },
            ],
        }
        try:
            response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
        except httpx.RequestError as exc:
            raise RuntimeError(summarize_httpx_exception(exc)) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(summarize_httpx_exception(exc)) from exc
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return text
        message = choices[0].get("message") or {}
        return (message.get("content") or text).strip()

    async def aclose(self) -> None:
        await self.client.aclose()

    def _style_block(self) -> str:
        if self.style == TranslationStyle.LIVE_COMMERCE:
            return (
                "【风格：直播带货】保留促销节奏与紧迫感，数字、价格、优惠、库存、链接口令等尽量原样或直译；"
                "口语叫卖感可略作润色但不要改成书面语；品牌名、SKU、人名保留常见写法。"
            )
        if self.style == TranslationStyle.COLLOQUIAL:
            return (
                "【风格：口语】用自然口语化的简体中文字幕，短句优先，像朋友聊天；"
                "避免公文腔和过度书面词，但不要用低俗或过度网络梗。"
            )
        return (
            "【风格：正式】用语规范、清晰，可用适度书面表达，适合新闻、演讲、正式解说；"
            "避免俚语与夸张促销话术，数字与专有名词准确。"
        )

    def _quality_block(self) -> str:
        return (
            "【译文质量】"
            "称谓：结合源语线索选「先生/女士/小姐」等，有女性身份或母职/女主播语境时不要默认「先生」。"
            "线上线下：源语表示网购、官网、直播链接、online、ออนไลน์、e-commerce 等时译为「线上/在线/网上」，不要反义成「线下」。"
            "地名：尽量使用通行中文译名；无把握时音译并在全篇保持一致。"
            "去重：禁止「也也是」「的的」等赘余叠词；若本句与上文高度同义，可压缩措辞，但勿删掉本句相对上文的新信息。"
            "听写疑点：残句或疑似听错时，在带货语境下可优先选择合理的商品/包装义项，勿引入与画面无关的荒诞引申。"
        )

    def _system_prompt(self) -> str:
        base = (
            "你是直播实时字幕翻译助手。"
            "你的任务是把当前这一句翻译成简体中文字幕。"
            "不要补写下一句，不要把上一句合并进来，不要总结，不要解释。"
            "遇到残句、口误、听不清、语义不完整时，宁可保守直译，也不要脑补。"
            "品牌名、人名、地名、商品名优先保留原文或做简短音译。"
            "输出只能是译文本身。"
        )
        precise = ""
        if self.recognition_mode == RecognitionMode.PRECISE:
            precise = (
                "【准确优先】当前为精准切分模式：请与源句一一对应，勿合并相邻语义。"
                "术语、数字、否定与语气尽量与源句对齐；不确定处保留原词或音译，勿凭空虚构。"
                "少用过度压缩的短词导致信息缺失。"
            )
        parts: list[str] = [base, self._quality_block()]
        domain = _DOMAIN_HINTS.get(self.translation_domain, "")
        if domain:
            parts.append(domain)
        parts.append(self._style_block())
        if precise:
            parts.append(precise)
        glossary = self._table_block("【术语与固定译法】以下条目在译文中请严格遵守（支持 原文=译文、外文=中文）。", self._glossary_lines)
        if glossary:
            parts.append(glossary)
        names = self._table_block("【人名/主播/昵称】以下写法在译文中请统一（支持 展示名=中文名、外文名=中文名）。", self._names_lines)
        if names:
            parts.append(names)
        return "\n".join(parts)

    def _table_block(self, title: str, lines: list[str]) -> str:
        if not lines:
            return ""
        body = "\n".join(f"- {line}" for line in lines)
        return f"{title}\n{body}"

    def _build_user_prompt(self, *, text: str, source_lang: str, context_lines: str) -> str:
        language_name = LANGUAGE_NAMES.get(source_lang, source_lang or "自动检测")
        return (
            f"源语言: {language_name}\n"
            f"上文参考:\n{context_lines}\n\n"
            f"当前这一句:\n{text}"
        )

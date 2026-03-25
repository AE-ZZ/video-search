import base64
import logging
import re
from pathlib import Path

from backend import config

logger = logging.getLogger(__name__)

# --- Module-level state ---
_backend = None  # "openai" or "local"
_openai_client = None
_text_model = None
_text_processor = None
_vision_model = None
_vision_processor = None
_vision_config = None


def init_openai():
    global _backend, _openai_client
    from openai import OpenAI
    _openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
    _backend = "openai"
    logger.info("LLM backend: OpenAI GPT-4o-mini")


def init_local():
    global _backend, _text_model, _text_processor
    global _vision_model, _vision_processor, _vision_config
    from mlx_lm import load as load_text
    from mlx_vlm import load as load_vision
    from mlx_vlm.utils import load_config

    logger.info(f"Loading text LLM: {config.LOCAL_LLM_TEXT} ...")
    _text_model, _text_processor = load_text(config.LOCAL_LLM_TEXT)

    logger.info(f"Loading vision LLM: {config.LOCAL_LLM_VISION} ...")
    _vision_model, _vision_processor = load_vision(config.LOCAL_LLM_VISION)
    _vision_config = load_config(config.LOCAL_LLM_VISION)

    _backend = "local"
    logger.info("LLM backend: local MLX (text: Qwen3.5-9B, vision: Qwen3-VL-8B)")


# --- Local MLX helpers ---

def _clean_output(result) -> str:
    text = result.text if hasattr(result, "text") else str(result)
    for stop in ["<|endoftext|>", "<|im_start|>", "<|im_end|>"]:
        text = text.split(stop)[0]
    # Strip thinking blocks (complete and incomplete)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)  # incomplete think block
    return text.strip()


def _build_chat_prompt(system: str | None, user: str) -> str:
    """Build chat prompt using the tokenizer's chat template with thinking disabled."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return _text_processor.apply_chat_template(
        messages, add_generation_prompt=True, enable_thinking=False,
    )


def _local_text_generate(prompt: str, max_tokens: int = 1024) -> str:
    from mlx_lm import generate
    result = generate(
        _text_model, _text_processor,
        prompt=prompt,
        max_tokens=max_tokens,
        verbose=False,
    )
    return _clean_output(result)


def _local_vision_generate(prompt: str, image_path: str, max_tokens: int = 300) -> str:
    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    formatted_prompt = apply_chat_template(
        _vision_processor, _vision_config, prompt, num_images=1,
    )
    result = generate(
        _vision_model, _vision_processor,
        formatted_prompt, [image_path],
        verbose=False,
        max_tokens=max_tokens,
    )
    return _clean_output(result)


# --- Public API ---

def summarize_transcript(transcript: str) -> str:
    prompt = (
        "Summarize the following video transcript concisely. "
        "Highlight the main topics, key points, and any notable moments. "
        "Use bullet points for clarity.\n\n"
        f"Transcript:\n{transcript[:50000]}"
    )

    if _backend == "local":
        chat_prompt = _build_chat_prompt(None, prompt)
        return _local_text_generate(chat_prompt, max_tokens=1024)

    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def answer_question(
    question: str,
    context_segments: list[dict],
    history: list[dict] | None = None,
) -> str:
    context = "\n".join(
        f"[{s['start_time']:.1f}s - {s['end_time']:.1f}s]: {s['text']}"
        for s in context_segments
    )

    system_msg = (
        "You are a helpful assistant that answers questions about video content "
        "based on transcript segments. Always cite timestamps when referencing "
        "specific parts of the video. If the transcript doesn't contain enough "
        "information to answer, say so honestly."
    )

    user_msg = (
        f"Based on the following transcript segments from a video, "
        f"answer the question. Cite the timestamps when referencing specific parts.\n\n"
        f"Transcript segments:\n{context}\n\n"
        f"Question: {question}"
    )

    if _backend == "local":
        chat_prompt = _build_chat_prompt(system_msg, user_msg)
        return _local_text_generate(chat_prompt, max_tokens=1024)

    messages = [{"role": "system", "content": system_msg}]
    if history:
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})

    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=messages,
    )
    return response.choices[0].message.content


def explain_text_match(query: str, text: str, start_time: float, end_time: float) -> str:
    prompt = (
        f"A user searched for \"{query}\" and the following transcript segment "
        f"was returned as a semantic match.\n\n"
        f"Transcript [{start_time:.1f}s - {end_time:.1f}s]: \"{text}\"\n\n"
        f"In one or two sentences, explain why this segment is related to the search query."
    )

    if _backend == "local":
        chat_prompt = _build_chat_prompt(None, prompt)
        return _local_text_generate(chat_prompt, max_tokens=200)

    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def explain_visual_match(query: str, frame_path: str, timestamp: float) -> str:
    path = Path(frame_path)
    if not path.exists():
        return "Frame image not available."

    prompt = (
        f"A user searched for \"{query}\" and this video frame at "
        f"{timestamp:.0f}s was returned as a visual match. "
        f"In one or two sentences, describe what you see in the frame "
        f"and explain why it relates to the search query."
    )

    if _backend == "local":
        return _local_vision_generate(prompt, str(path), max_tokens=200)

    # OpenAI vision
    with open(path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    response = _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
    )
    return response.choices[0].message.content

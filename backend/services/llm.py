import base64
from pathlib import Path

from openai import OpenAI

from backend.config import OPENAI_API_KEY


def get_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def summarize_transcript(transcript: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                "Summarize the following video transcript concisely. "
                "Highlight the main topics, key points, and any notable moments. "
                "Use bullet points for clarity.\n\n"
                f"Transcript:\n{transcript[:50000]}"
            ),
        }],
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

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that answers questions about video content "
                "based on transcript segments. Always cite timestamps when referencing "
                "specific parts of the video. If the transcript doesn't contain enough "
                "information to answer, say so honestly."
            ),
        },
    ]

    if history:
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({
        "role": "user",
        "content": (
            f"Based on the following transcript segments from a video, "
            f"answer the question. Cite the timestamps when referencing specific parts.\n\n"
            f"Transcript segments:\n{context}\n\n"
            f"Question: {question}"
        ),
    })

    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=messages,
    )
    return response.choices[0].message.content


def explain_text_match(query: str, text: str, start_time: float, end_time: float) -> str:
    """Explain why a transcript segment is semantically related to the query."""
    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                f"A user searched for \"{query}\" and the following transcript segment "
                f"was returned as a semantic match.\n\n"
                f"Transcript [{start_time:.1f}s - {end_time:.1f}s]: \"{text}\"\n\n"
                f"In one or two sentences, explain why this segment is related to the search query."
            ),
        }],
    )
    return response.choices[0].message.content


def explain_visual_match(query: str, frame_path: str, timestamp: float) -> str:
    """Explain why a video frame visually matches the query using GPT-4o-mini vision."""
    path = Path(frame_path)
    if not path.exists():
        return "Frame image not available."

    with open(path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"A user searched for \"{query}\" and this video frame at "
                        f"{timestamp:.0f}s was returned as a visual match. "
                        f"In one or two sentences, describe what you see in the frame "
                        f"and explain why it relates to the search query."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
            ],
        }],
    )
    return response.choices[0].message.content

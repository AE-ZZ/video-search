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

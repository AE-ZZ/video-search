from pathlib import Path

import open_clip
import torch
from PIL import Image

from backend.config import CLIP_MODEL, CLIP_PRETRAINED


def load_clip_model():
    model, _, preprocess = open_clip.create_model_and_transforms(
        CLIP_MODEL, pretrained=CLIP_PRETRAINED,
    )
    tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
    model.eval()
    return model, preprocess, tokenizer


def embed_images(model, preprocess, image_paths: list[Path]) -> list[list[float]]:
    images = []
    for p in image_paths:
        img = Image.open(p).convert("RGB")
        images.append(preprocess(img))

    batch = torch.stack(images)
    with torch.no_grad():
        features = model.encode_image(batch)
        features = features / features.norm(dim=-1, keepdim=True)

    return features.tolist()


def embed_text_query(model, tokenizer, text: str) -> list[float]:
    tokens = tokenizer([text])
    with torch.no_grad():
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)

    return features[0].tolist()

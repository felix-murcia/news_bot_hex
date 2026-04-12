"""
Training script for Classic News Validator (TF-IDF + LogisticRegression).

Run once offline to produce the pre-trained model.
The model is then used by the pipeline for fast CPU-based classification.

Usage:
    python scripts/train_news_validator.py --dataset data/fake_news_dataset.csv
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.news.domain.services.classic_news_validator import ClassicNewsValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("train_validator")


def load_dataset_kaggle_fake_news(csv_path: str):
    """
    Load the Kaggle Fake News dataset.
    Expected columns: 'title', 'text', 'label' (0=FAKE, 1=REAL)
    """
    import csv

    texts = []
    labels = []

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("title", "") or ""
            text = row.get("text", "") or ""
            label_val = row.get("label", "")

            if not label_val or label_val not in ("0", "1"):
                continue

            combined = f"{title}. {text[:2000]}"
            label = "REAL" if label_val == "1" else "FAKE"

            texts.append(combined)
            labels.append(label)

    logger.info(f"Loaded {len(texts)} samples from {csv_path}")
    label_counts = {}
    for l in labels:
        label_counts[l] = label_counts.get(l, 0) + 1
    logger.info(f"Label distribution: {label_counts}")

    return texts, labels


def load_dataset_isot(csv_path: str):
    """
    Load the LIAR dataset (isot).
    Expected columns: 'label' (true/false/half-true/etc), 'statement'
    """
    import csv

    texts = []
    labels = []

    true_labels = {"true", "mostly-true"}
    false_labels = {"false", "pants-fire"}

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            statement = row.get("statement", "") or ""
            label_val = (row.get("label", "") or "").strip().lower()

            if label_val in true_labels:
                texts.append(statement)
                labels.append("REAL")
            elif label_val in false_labels:
                texts.append(statement)
                labels.append("FAKE")

    logger.info(f"Loaded {len(texts)} samples from {csv_path}")
    label_counts = {}
    for l in labels:
        label_counts[l] = label_counts.get(l, 0) + 1
    logger.info(f"Label distribution: {label_counts}")

    return texts, labels


def main():
    parser = argparse.ArgumentParser(description="Train Classic News Validator")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to CSV dataset",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="kaggle",
        choices=["kaggle", "isot", "auto"],
        help="Dataset format",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output model directory (default: models/news_validator/)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.dataset):
        logger.error(f"Dataset not found: {args.dataset}")
        sys.exit(1)

    # Load dataset
    if args.format == "kaggle":
        texts, labels = load_dataset_kaggle_fake_news(args.dataset)
    elif args.format == "isot":
        texts, labels = load_dataset_isot(args.dataset)
    else:
        # Auto-detect
        texts, labels = load_dataset_kaggle_fake_news(args.dataset)

    if len(texts) < 100:
        logger.error("Not enough samples (need at least 100)")
        sys.exit(1)

    # Train
    model_path = args.output or "models/news_validator"
    validator = ClassicNewsValidator(model_path=model_path)
    validator.train(texts, labels)

    # Quick evaluation
    logger.info("Running quick evaluation on training data...")
    correct = 0
    for text, label in zip(texts[:500], labels[:500]):
        title_part = text.split(".")[0] if "." in text else text[:100]
        desc_part = text[len(title_part) + 1:] if "." in text else ""
        is_real, conf = validator.predict(title_part, desc_part)
        predicted_label = "REAL" if is_real else "FAKE"
        if predicted_label == label:
            correct += 1

    accuracy = correct / min(500, len(texts))
    logger.info(f"Training accuracy (first 500 samples): {accuracy:.2%}")
    logger.info(f"Model saved to: {model_path}/news_validator.pkl")


if __name__ == "__main__":
    main()

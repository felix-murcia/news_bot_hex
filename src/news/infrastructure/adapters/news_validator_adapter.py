"""
Adapter that wraps ClassicNewsValidator to implement the FakeNewsModel port.

ML model loading (joblib, sklearn) lives here in infrastructure.
Pure heuristic rules live in the domain layer.
"""

import logging
import os
from typing import List, Tuple

from src.news.domain.ports import FakeNewsModel
from src.news.domain.services.classic_news_validator import (
    preprocess_text,
    heuristic_predict,
)

logger = logging.getLogger(__name__)


class ClassicNewsValidatorAdapter(FakeNewsModel):
    """
    Infrastructure adapter: ClassicNewsValidator -> FakeNewsModel port.

    Loads a pre-trained ML model from disk if available.
    Falls back to pure heuristic rules from the domain layer.
    """

    LABEL_REAL = "REAL"
    LABEL_FAKE = "FAKE"

    def __init__(self, model_path: str = None):
        from config.settings import Settings

        self._model_path = model_path or str(Settings.FAKE_NEWS_MODEL_DIR)
        self._pipeline = None
        self._loaded = False
        self._load_model()

    def _load_model(self) -> bool:
        """Load pre-trained model from disk."""
        if self._loaded:
            return True

        try:
            import joblib
        except ImportError:
            logger.warning("[FAKE_NEWS] joblib not available, using heuristic fallback")
            self._loaded = True
            return False

        if not os.path.isdir(self._model_path):
            logger.debug(f"[FAKE_NEWS] Model directory not found: {self._model_path}")
            self._loaded = True
            return False

        model_file = os.path.join(self._model_path, "news_validator.pkl")
        if not os.path.exists(model_file):
            logger.debug(f"[FAKE_NEWS] Model file not found: {model_file}")
            self._loaded = True
            return False

        try:
            self._pipeline = joblib.load(model_file)
            self._loaded = True
            logger.info(f"[FAKE_NEWS] ML model loaded from: {model_file}")
            return True
        except Exception as e:
            logger.warning(f"[FAKE_NEWS] Error loading model: {e}, using heuristic fallback")
            self._loaded = True
            return False

    def predict(self, title: str, desc: str) -> Tuple[bool, float]:
        text = f"{title}. {desc}"

        if self._pipeline is not None:
            processed = preprocess_text(text)
            prediction = self._pipeline.predict([processed])[0]
            proba = self._pipeline.predict_proba([processed])[0]
            confidence = float(max(proba))
            is_real = (prediction == self.LABEL_REAL)
            logger.debug(
                f"[FAKE_NEWS] ML: '{title[:60]}...' → real={is_real}, "
                f"conf={confidence:.4f}"
            )
            return is_real, confidence

        # Fallback to pure domain heuristic
        is_real, confidence = heuristic_predict(text)
        logger.debug(
            f"[FAKE_NEWS] Heuristic: '{title[:60]}...' → real={is_real}, "
            f"conf={confidence:.4f}"
        )
        return is_real, confidence

    def predict_batch(self, texts: List[str]) -> Tuple[List[bool], List[float]]:
        results = [self.predict(t, "") for t in texts]
        return [r[0] for r in results], [r[1] for r in results]

"""A no-download blank spaCy NLP engine for Presidio's deterministic layer."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import spacy
from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine
from spacy.language import Language


class BlankSpacyNlpEngine(NlpEngine):
    """Tokenize Turkish and English without loading a statistical model."""

    def __init__(self) -> None:
        self._pipelines: dict[str, Language] = {}

    def load(self) -> None:
        if not self._pipelines:
            self._pipelines = {"tr": spacy.blank("tr"), "en": spacy.blank("en")}

    def is_loaded(self) -> bool:
        return set(self._pipelines) == {"tr", "en"}

    def process_text(self, text: str, language: str) -> NlpArtifacts:
        if not self.is_loaded():
            self.load()
        pipeline = self._pipelines.get(language)
        if pipeline is None:
            raise ValueError(f"unsupported language: {language}")
        doc = pipeline(text)
        return NlpArtifacts(
            entities=[],
            tokens=doc,
            tokens_indices=[token.idx for token in doc],
            lemmas=[token.text for token in doc],
            nlp_engine=self,
            language=language,
            scores=[],
        )

    def process_batch(
        self,
        texts: Iterable[str],
        language: str,
        batch_size: int = 1,
        n_process: int = 1,
        **kwargs: object,
    ) -> Iterator[tuple[str, NlpArtifacts]]:
        del batch_size, n_process, kwargs
        for text in texts:
            yield text, self.process_text(text, language)

    def is_stopword(self, word: str, language: str) -> bool:
        pipeline = self._pipelines.get(language)
        return pipeline is not None and pipeline.vocab[word].is_stop

    def is_punct(self, word: str, language: str) -> bool:
        pipeline = self._pipelines.get(language)
        return pipeline is not None and pipeline.vocab[word].is_punct

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["tr", "en"]

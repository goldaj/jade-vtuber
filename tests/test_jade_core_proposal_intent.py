"""Regression: explicit Core requests are proposals and not mandatory L2 writes."""
import pytest

from src.jade_runtime.explicit_memory_intent import parse_explicit_memory_intent


@pytest.mark.parametrize("phrase", [
    "Jade, enregistre dans tes Core Memories que tu es née en 2025.",
    "Jade, mets dans ta mémoire de niveau 3 que tu es née en 2025.",
    "Jade, mets dans ton core memory que tu es née en 2025.",
    "Jade, ajoute en souvenirs de niveau 3 que tu es née en 2025.",
    "Jade, conserve dans tes souvenirs fondateurs que tu es née en 2025.",
    "Jade, garde comme core memories que tu es née en 2025.",
])
def test_explicit_core_request_is_only_a_proposal(phrase):
    intent = parse_explicit_memory_intent(phrase)
    assert intent is not None and intent.requested_core is True
    assert "2025" in intent.summary


@pytest.mark.parametrize("phrase", [
    "Goldaj : Retiens que je commence le piano.",
    "Jade, enregistre dans ta mémoire ordinaire que je commence le piano.",
    "Jade, note dans tes souvenirs que je commence le piano.",
])
def test_explicit_ordinary_level_2_request_is_still_mandatory_for_owner(phrase):
    intent = parse_explicit_memory_intent(phrase)
    assert intent is not None
    assert intent.requested_core is False
    assert "piano" in intent.summary

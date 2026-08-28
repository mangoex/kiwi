from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_openrouter_secret_stays_in_backend_and_endpoint_is_canonical() -> None:
    api = (ROOT / "apps/api/restaurant_os/api.py").read_text(encoding="utf-8")
    config = (ROOT / "apps/api/restaurant_os/config.py").read_text(encoding="utf-8")
    pos = (ROOT / "apps/pos-web/src/features/pos/PointOfSale.tsx").read_text(encoding="utf-8")

    assert '"/orders/assisted-draft"' in api
    assert '"pos.operate"' in api
    assert "openrouter_api_key" in config
    assert "OPENROUTER_API_KEY" not in pos
    assert "VITE_OPENROUTER" not in pos
    assert "'/orders/assisted-draft'" in pos


def test_assisted_trigger_is_icon_only_and_accessible() -> None:
    pos = (ROOT / "apps/pos-web/src/features/pos/PointOfSale.tsx").read_text(encoding="utf-8")
    styles = (ROOT / "apps/pos-web/src/App.css").read_text(encoding="utf-8")
    trigger = pos.split('className="pos-assisted-trigger"', 1)[1].split("</button>", 1)[0]

    assert 'aria-label="Abrir Pedido asistido"' in trigger
    assert 'title="Pedido asistido"' in trigger
    assert "Captura asistida" not in trigger
    assert ".pos-assisted-trigger" in styles
    assert "width: 44px" in styles and "height: 44px" in styles


def test_dialog_blocks_apply_until_required_questions_are_complete() -> None:
    pos = (ROOT / "apps/pos-web/src/features/pos/PointOfSale.tsx").read_text(encoding="utf-8")
    helper = (ROOT / "apps/pos-web/src/features/pos/assistedOrderDraft.ts").read_text(
        encoding="utf-8"
    )

    assert "isAssistedDraftComplete(assistedDraft)" in pos
    assert "toggleAssistedOption" in pos
    assert "question.minimum_selections" in helper
    assert "question.maximum_selections" in helper
    assert "disabled={!isAssistedDraftComplete(assistedDraft)" in pos


def test_dictation_uses_browser_capability_without_easypanel_build_argument() -> None:
    pos = (ROOT / "apps/pos-web/src/features/pos/PointOfSale.tsx").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "'SpeechRecognition' in window" in pos
    assert 'aria-pressed={assistedDictating}' in pos
    assert "VITE_POS_ASSISTED_DICTATION_ENABLED" not in pos
    assert "VITE_POS_ASSISTED_DICTATION_ENABLED" not in dockerfile

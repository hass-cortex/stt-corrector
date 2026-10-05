"""Tests for approving a learned replacement rule through Repairs."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.stt_corrector.mishearing import Fix, FixPlan
from custom_components.stt_corrector.models import STTCorrectorRuntimeData
from custom_components.stt_corrector.repairs import (
    LearnedRuleRepairFlow,
    async_create_fix_flow,
    learned_rule_issue_id,
)

DATA = {
    "entry_id": "entry-1",
    "heard": "打開力戰",
    "meant": "打開立扇",
    "raw": "打開力戰。",
    "locale": "zh-TW",
    "wrong": "力戰",
    "right": "立扇",
}
RULE = Fix("replacement", "力戰", "立扇")


def _flow(mock_hass, plan: FixPlan) -> LearnedRuleRepairFlow:
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.title = "SenseVoice Small Corrected"
    entity = MagicMock()
    entity.entity_id = "stt.sensevoice_small_corrected"
    entity.async_plan_mishearing_fix = AsyncMock(return_value=plan)
    entry.runtime_data = STTCorrectorRuntimeData(entity=entity)
    flow = LearnedRuleRepairFlow(entry, dict(DATA))
    flow.hass = mock_hass
    return flow


async def _approve(flow):
    with patch(
        "custom_components.stt_corrector.services.async_apply_learned_fix",
        new=AsyncMock(),
    ) as apply:
        result = await flow.async_step_confirm({})
    return result, apply


class TestLearnedRuleRepairFlow:
    @pytest.mark.asyncio
    async def test_shows_the_rule_before_applying(self, mock_hass):
        flow = _flow(mock_hass, FixPlan("fix", "打開立扇", RULE))
        result = await flow.async_step_init(DATA)
        assert result["step_id"] == "confirm"
        placeholders = result["description_placeholders"]
        assert (placeholders["wrong"], placeholders["right"]) == ("力戰", "立扇")
        flow._entry.runtime_data.entity.async_plan_mishearing_fix.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_applies_the_approved_rule_after_replanning(self, mock_hass):
        flow = _flow(mock_hass, FixPlan("fix", "打開立扇", RULE))
        result, apply = await _approve(flow)
        assert result["type"] == "create_entry"
        flow._entry.runtime_data.entity.async_plan_mishearing_fix.assert_awaited_once_with(
            "打開力戰。", "打開立扇", "zh-TW"
        )
        apply.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_safer_phrase_is_applied_instead(self, mock_hass):
        phrase = FixPlan("fix", "打開立扇", Fix("phrase", "力戰", "立扇"))
        result, apply = await _approve(_flow(mock_hass, phrase))
        assert result["type"] == "create_entry"
        apply.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_different_rule_is_not_applied(self, mock_hass):
        other = FixPlan("fix", "打開立扇", Fix("replacement", "開力戰", "開立扇"))
        result, apply = await _approve(_flow(mock_hass, other))
        assert result["reason"] == "learned_rule_invalid"
        apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nothing_to_do_once_already_corrected(self, mock_hass):
        result, apply = await _approve(
            _flow(mock_hass, FixPlan("already_corrected", "打開立扇"))
        )
        assert result["type"] == "create_entry"
        apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejected_on_replan_aborts_with_the_reason(self, mock_hass):
        rejected = FixPlan("rejected", "打開力戰", reason="would also change 1 text")
        result, apply = await _approve(_flow(mock_hass, rejected))
        assert result["reason"] == "learned_rule_invalid"
        assert "would also change" in result["description_placeholders"]["reason"]
        apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fix_flow_dispatches_by_issue_id(self, mock_hass):
        entry = MagicMock()
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        flow = await async_create_fix_flow(
            mock_hass, learned_rule_issue_id("entry-1", "力戰"), dict(DATA)
        )
        assert isinstance(flow, LearnedRuleRepairFlow)

    def test_issue_id_is_stable_and_ascii(self):
        issue_id = learned_rule_issue_id("entry-1", "力戰")
        assert issue_id == learned_rule_issue_id("entry-1", "力戰")
        assert issue_id.isascii()

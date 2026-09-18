# Tests for tools_lambda/tools/kb.py: check_KB, update_KB.
import json
from unittest.mock import patch, MagicMock

from tools_lambda.tools.kb import check_KB, update_KB, THRESHOLD


def _fake_bedrock_response(embedding):
    body = MagicMock()
    body.read.return_value = json.dumps({"embedding": embedding}).encode()
    return {"body": body}


def test_check_KB_filters_by_threshold():
    matches = [
        {"content": "We open at 9am", "similarity": 0.9},
        {"content": "Irrelevant", "similarity": 0.5},
    ]
    with patch("tools_lambda.tools.kb.bedrock.invoke_model", return_value=_fake_bedrock_response([0.1, 0.2, 0.3])), \
    patch("tools_lambda.tools.kb.get_matching_kb_contents", return_value=matches):
        result = check_KB("what time do you open")
    assert result == [{"content": "We open at 9am", "similarity": 0.9}]


def test_check_KB_excludes_exact_threshold_match():
    matches = [{"content": "Borderline", "similarity": THRESHOLD}]
    with patch("tools_lambda.tools.kb.bedrock.invoke_model", return_value=_fake_bedrock_response([0.1, 0.2, 0.3])), \
    patch("tools_lambda.tools.kb.get_matching_kb_contents", return_value=matches):
        result = check_KB("borderline query")
    assert result == []


def test_check_KB_returns_empty_when_nothing_above_threshold():
    matches = [{"content": "Irrelevant", "similarity": 0.5}]
    with patch("tools_lambda.tools.kb.bedrock.invoke_model", return_value=_fake_bedrock_response([0.1, 0.2, 0.3])), \
    patch("tools_lambda.tools.kb.get_matching_kb_contents", return_value=matches):
        result = check_KB("random query")
    assert result == []


def test_check_KB_passes_embedding_to_matcher():
    with patch("tools_lambda.tools.kb.bedrock.invoke_model", return_value=_fake_bedrock_response([0.1, 0.2, 0.3])), \
    patch("tools_lambda.tools.kb.get_matching_kb_contents", return_value=[]) as mock_match:
        check_KB("what time do you open")
    mock_match.assert_called_once_with([0.1, 0.2, 0.3])


def test_update_KB_embeds_each_unembedded_row():
    kb_rows = [
        {"restaurant_kb_id": "id-1", "content": "Fact one"},
        {"restaurant_kb_id": "id-2", "content": "Fact two"},
    ]
    with patch("tools_lambda.tools.kb.get_kb_content", return_value=kb_rows), \
    patch("tools_lambda.tools.kb.bedrock.invoke_model", return_value=_fake_bedrock_response([0.5, 0.6])), \
    patch("tools_lambda.tools.kb.update_kb_content", return_value={"updated": True}) as mock_update:
        result = update_KB()
    assert mock_update.call_count == 2
    mock_update.assert_any_call("id-1", [0.5, 0.6])
    mock_update.assert_any_call("id-2", [0.5, 0.6])
    assert result == [{"updated": True}, {"updated": True}]


def test_update_KB_when_nothing_to_embed():
    with patch("tools_lambda.tools.kb.get_kb_content", return_value=[]), \
    patch("tools_lambda.tools.kb.bedrock.invoke_model") as mock_invoke:
        result = update_KB()
    mock_invoke.assert_not_called()
    assert result == []

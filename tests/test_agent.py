# # Tests for the agent's system prompt and Agent construction.
# from pathlib import Path

# SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "agent" / "prompts" / "system_prompt.md"


# def test_system_prompt_exists_and_not_empty():
#     assert SYSTEM_PROMPT_PATH.is_file()
#     assert SYSTEM_PROMPT_PATH.read_text().strip() != ""


# def test_system_prompt_mentions_booking_not_available():
#     content = SYSTEM_PROMPT_PATH.read_text().lower()
#     assert "booking isn't available in this preview" in content


# def test_system_prompt_mentions_cannot_check_availability():
#     content = SYSTEM_PROMPT_PATH.read_text().lower()
#     assert "cannot check real-time table availability" in content


# def test_system_prompt_mentions_saravana_bhavan():
#     content = SYSTEM_PROMPT_PATH.read_text().lower()
#     assert "saravana bhavan" in content


# def test_agent_constructs_without_raising():
#     from agent.agent import Agent

#     Agent()

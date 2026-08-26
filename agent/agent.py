# Strands agent definition, deployed to AgentCore Runtime.
from pathlib import Path
from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel

load_dotenv()

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text()

# model = BedrockModel(model_id="anthropic.claude-haiku-4-5-20251001-v1:0")amazon.nova-2-lite-v1:0
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)


if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            break
        response = agent(user_input)
        print(response)

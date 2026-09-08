# check_KB, update_KB.
from shared.queries import get_kb_content, update_kb_content, get_matching_kb_contents
import json
import boto3

bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

THRESHOLD = 0.75

model_id = "amazon.titan-embed-text-v1"


def check_KB(topic: str) -> list[dict]:
    
    # Prepare the input payload
    payload = {
        "inputText": topic,
        "dimensions": 1536,
        "normalize": True
    }
    
    # Invoke the model
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )

        # Parse the response body
    response_body = json.loads(response["body"].read())
    matching_answers = get_matching_kb_contents(response_body["embedding"])

    results_above_thershold = []
    for c in range(len(matching_answers)):
        if matching_answers[c]["similarity"] > THRESHOLD:
            results_above_thershold.append(matching_answers[c])
    return results_above_thershold

def update_KB() -> list[dict]:
    kb_content = get_kb_content()

    result = []
    for cont in range(len(kb_content)):
        # Prepare the input payload
        payload = {
            "inputText": kb_content[cont]["content"],
            "dimensions": 1536,
            "normalize": True
        }

        # Invoke the model
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )

        # Parse the response body
        response_body = json.loads(response["body"].read())
        embedding_vector = update_kb_content(kb_content[cont]["restaurant_kb_id"], response_body["embedding"])
        result.append(embedding_vector)
    return result




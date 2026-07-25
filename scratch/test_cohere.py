import boto3
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("BEDROCK_REGION", "ap-southeast-1"),
    aws_access_key_id=os.getenv("2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("2_SECRET_ACCESS_KEY")
)

try:
    response = client.invoke_model(
        modelId="cohere.embed-multilingual-v3",
        body=json.dumps({"texts": ["Hello world"], "input_type": "search_document"}),
        contentType="application/json",
        accept="application/json"
    )
    print("Cohere success")
except Exception as e:
    print(f"Cohere error: {e}")

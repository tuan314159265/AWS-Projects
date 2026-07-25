import boto3
import os
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
        modelId="amazon.titan-embed-text-v1",
        body=b'{"inputText": "Hello world"}'
    )
    print("V1 success")
except Exception as e:
    print(f"V1 error: {e}")

try:
    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=b'{"inputText": "Hello world"}'
    )
    print("V2 success")
except Exception as e:
    print(f"V2 error: {e}")

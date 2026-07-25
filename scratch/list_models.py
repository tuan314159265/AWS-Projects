import boto3
import os
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    "bedrock",
    region_name=os.getenv("BEDROCK_REGION", "ap-southeast-1"),
    aws_access_key_id=os.getenv("2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("2_SECRET_ACCESS_KEY")
)

try:
    response = client.list_foundation_models()
    models = response['modelSummaries']
    for model in models:
        print(model['modelId'])
except Exception as e:
    print(f"Error: {e}")

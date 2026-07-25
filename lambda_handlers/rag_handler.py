"""
Lambda handler cho RAG API.
Được trigger bởi API Gateway (POST /query).
"""
import json
from search.engine import Pipeline

# Khởi tạo pipeline NGOÀI handler để tận dụng warm start
pipeline = Pipeline()

def handler(event, context):
    """Lambda entry point cho RAG query."""
    try:
        body = json.loads(event.get("body", "{}"))
        query = body.get("query", "")
        model = body.get("model", "default")
        
        if not query:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "query is required"})
            }
        
        response = pipeline.ask(query=query, model=model)
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "query": response.query,
                "summary": response.summary,
                "total": response.total,
                "duration_ms": response.duration_ms,
                "results": [
                    {
                        "id": hit.id,
                        "title": hit.title,
                        "content": hit.content,
                        "url": hit.url,
                        "score": hit.score
                    }
                    for hit in response.results
                ]
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"[ERROR] RAG query failed: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Internal server error"})
        }

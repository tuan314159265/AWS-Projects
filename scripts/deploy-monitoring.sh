#!/usr/bin/env bash
set -euo pipefail
# Deploy CloudWatch monitoring: dashboard, alarms, log metric filters

REGION="${AWS_REGION:-ap-southeast-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "=== CloudWatch Dashboard ==="
aws cloudwatch put-dashboard --dashboard-name NewsRAG-Overview --dashboard-body "{
  \"widgets\": [
    {\"type\":\"metric\",\"x\":0,\"y\":0,\"w\":12,\"h\":6,\"properties\":{
      \"metrics\":[[\"NewsRAG\",\"SearchDuration\",{\"stat\":\"Average\"}],[\"...\",{\"stat\":\"p99\"}]],
      \"period\":300,\"stat\":\"Average\",\"region\":\"$REGION\",\"title\":\"API Latency (ms)\"}},
    {\"type\":\"metric\",\"x\":12,\"y\":0,\"w\":6,\"h\":6,\"properties\":{
      \"metrics\":[[\"NewsRAG\",\"SearchHitCount\",{\"stat\":\"Sum\"}]],
      \"period\":300,\"stat\":\"Sum\",\"region\":\"$REGION\",\"title\":\"Search QPS\"}},
    {\"type\":\"metric\",\"x\":18,\"y\":0,\"w\":6,\"h\":6,\"properties\":{
      \"metrics\":[[\"AWS/RDS\",\"DatabaseConnections\",{\"stat\":\"Average\",\"label\":\"RDS Connections\"}]],
      \"period\":300,\"stat\":\"Average\",\"region\":\"$REGION\",\"title\":\"DB Connections\"}},
    {\"type\":\"metric\",\"x\":0,\"y\":6,\"w\":8,\"h\":6,\"properties\":{
      \"metrics\":[[\"AWS/ECS\",\"CPUUtilization\",{\"stat\":\"Average\"}],[\".\",\".\",\"MemoryUtilization\",{\"stat\":\"Average\"}]],
      \"period\":300,\"stat\":\"Average\",\"region\":\"$REGION\",\"title\":\"ECS CPU/Memory\"}}
  ]
}"
echo "  Dashboard created"

echo "=== Metric Filters ==="
# Log-based metrics
aws logs put-metric-filter \
  --log-group-name /ecs/newsrag-project \
  --filter-name SearchDuration \
  --filter-pattern '"[METRIC] search_duration_ms"' \
  --metric-transformations metricName=SearchDurationLog,metricNamespace=NewsRAG,metricValue=\$duration

aws logs put-metric-filter \
  --log-group-name /ecs/newsrag-project \
  --filter-name SearchError \
  --filter-pattern '"ERROR"' \
  --metric-transformations metricName=ErrorCount,metricNamespace=NewsRAG,metricValue=1

echo "=== Alarms ==="
aws cloudwatch put-metric-alarm \
  --alarm-name NewsRAG-RDS-HighCPU \
  --alarm-description \"RDS CPU > 80 for 5 min\" \
  --metric-name CPUUtilization --namespace AWS/RDS \
  --statistic Average --period 300 --evaluation-periods 2 \
  --threshold 80 --comparison-operator GreaterThanThreshold \
  --dimensions Name=DBInstanceIdentifier,Value=newsrag-postgres-1 \
  --alarm-actions arn:aws:sns:$REGION:$ACCOUNT_ID:NewsRAG-Alerts

aws cloudwatch put-metric-alarm \
  --alarm-name NewsRAG-5xx \
  --alarm-description \"5xx errors > 10/min\" \
  --metric-name ErrorCount --namespace NewsRAG \
  --statistic Sum --period 60 --evaluation-periods 2 \
  --threshold 10 --comparison-operator GreaterThanThreshold

echo "=== Done ==="
# ============================================================================
# NewsRAG — CloudWatch Monitoring Setup (AWS CLI)
# Region: ap-southeast-2
# ============================================================================

$REGION = "ap-southeast-2"
$ACCOUNT_ID = "814808959551"
$ALERT_EMAIL = "nguyenletrong91@gmail.com"

# Lambda function names
$LAMBDA_RAG = "newsrag-rag-api"
$LAMBDA_ETL = "newsrag-etl"

# RDS
$RDS_CLUSTER = "newsrag-postgres"
$RDS_INSTANCE = "newsrag-postgres-1"

# SQS
$SQS_DLQ = "newsrag-raw-news-dlq"

# Log Group
$LOG_GROUP = "/ecs/newsrag-project"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " NewsRAG CloudWatch Monitoring Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# ============================================================================
# 1. SNS TOPIC + EMAIL SUBSCRIPTION
# ============================================================================
Write-Host "`n[1/5] Creating SNS Topic..." -ForegroundColor Yellow

$SNS_ARN = aws sns create-topic `
    --name newsrag-alarm-topic `
    --region $REGION `
    --query "TopicArn" `
    --output text

Write-Host "  SNS Topic ARN: $SNS_ARN" -ForegroundColor Green

Write-Host "  Subscribing email: $ALERT_EMAIL"
aws sns subscribe `
    --topic-arn $SNS_ARN `
    --protocol email `
    --notification-endpoint $ALERT_EMAIL `
    --region $REGION

Write-Host "  [!] Check your email and CONFIRM the subscription!" -ForegroundColor Red

# ============================================================================
# 2. CLOUDWATCH METRIC FILTERS
# ============================================================================
Write-Host "`n[2/5] Creating Metric Filters..." -ForegroundColor Yellow

# Filter: Pipeline Errors (from ECS logs)
aws logs put-metric-filter `
    --log-group-name $LOG_GROUP `
    --filter-name "newsrag-pipeline-errors" `
    --filter-pattern "[ERROR]" `
    --metric-transformations "metricName=PipelineErrorCount,metricNamespace=NewsRAG/Pipeline,metricValue=1,defaultValue=0" `
    --region $REGION

Write-Host "  Created: newsrag-pipeline-errors" -ForegroundColor Green

# Filter: Pipeline Success (from ECS logs)
aws logs put-metric-filter `
    --log-group-name $LOG_GROUP `
    --filter-name "newsrag-pipeline-success" `
    --filter-pattern "[OK]" `
    --metric-transformations "metricName=PipelineSuccessCount,metricNamespace=NewsRAG/Pipeline,metricValue=1,defaultValue=0" `
    --region $REGION

Write-Host "  Created: newsrag-pipeline-success" -ForegroundColor Green

# ============================================================================
# 3. CLOUDWATCH ALARMS
# ============================================================================
Write-Host "`n[3/5] Creating CloudWatch Alarms..." -ForegroundColor Yellow

# --- Alarm 1: Lambda RAG Errors ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-lambda-rag-errors" `
    --alarm-description "Lambda RAG co >3 errors trong 5 phut" `
    --namespace "AWS/Lambda" `
    --metric-name "Errors" `
    --dimensions "Name=FunctionName,Value=$LAMBDA_RAG" `
    --statistic Sum `
    --period 300 `
    --evaluation-periods 1 `
    --threshold 3 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --ok-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-lambda-rag-errors" -ForegroundColor Green

# --- Alarm 2: Lambda ETL Errors ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-lambda-etl-errors" `
    --alarm-description "Lambda ETL co >1 error trong 5 phut" `
    --namespace "AWS/Lambda" `
    --metric-name "Errors" `
    --dimensions "Name=FunctionName,Value=$LAMBDA_ETL" `
    --statistic Sum `
    --period 300 `
    --evaluation-periods 1 `
    --threshold 1 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --ok-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-lambda-etl-errors" -ForegroundColor Green

# --- Alarm 3: Lambda RAG Duration (Latency) ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-lambda-rag-duration" `
    --alarm-description "Lambda RAG p99 latency > 10 giay" `
    --namespace "AWS/Lambda" `
    --metric-name "Duration" `
    --dimensions "Name=FunctionName,Value=$LAMBDA_RAG" `
    --extended-statistic p99 `
    --period 300 `
    --evaluation-periods 2 `
    --threshold 10000 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-lambda-rag-duration" -ForegroundColor Green

# --- Alarm 4: RDS CPU Utilization ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-rds-cpu-high" `
    --alarm-description "RDS Aurora CPU > 80% trong 10 phut" `
    --namespace "AWS/RDS" `
    --metric-name "CPUUtilization" `
    --dimensions "Name=DBClusterIdentifier,Value=$RDS_CLUSTER" `
    --statistic Average `
    --period 300 `
    --evaluation-periods 2 `
    --threshold 80 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --ok-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-rds-cpu-high" -ForegroundColor Green

# --- Alarm 5: RDS Database Connections ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-rds-connections-high" `
    --alarm-description "RDS connections > 50" `
    --namespace "AWS/RDS" `
    --metric-name "DatabaseConnections" `
    --dimensions "Name=DBClusterIdentifier,Value=$RDS_CLUSTER" `
    --statistic Average `
    --period 300 `
    --evaluation-periods 1 `
    --threshold 50 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --ok-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-rds-connections-high" -ForegroundColor Green

# --- Alarm 6: SQS DLQ Messages ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-sqs-dlq-not-empty" `
    --alarm-description "Co messages trong DLQ = co loi xu ly" `
    --namespace "AWS/SQS" `
    --metric-name "ApproximateNumberOfMessagesVisible" `
    --dimensions "Name=QueueName,Value=$SQS_DLQ" `
    --statistic Sum `
    --period 300 `
    --evaluation-periods 1 `
    --threshold 0 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --ok-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-sqs-dlq-not-empty" -ForegroundColor Green

# --- Alarm 7: Pipeline Errors (Custom Metric from Logs) ---
aws cloudwatch put-metric-alarm `
    --alarm-name "newsrag-pipeline-errors" `
    --alarm-description "ECS pipeline logs co [ERROR]" `
    --namespace "NewsRAG/Pipeline" `
    --metric-name "PipelineErrorCount" `
    --statistic Sum `
    --period 300 `
    --evaluation-periods 1 `
    --threshold 0 `
    --comparison-operator GreaterThanThreshold `
    --alarm-actions $SNS_ARN `
    --ok-actions $SNS_ARN `
    --treat-missing-data notBreaching `
    --region $REGION

Write-Host "  Created: newsrag-pipeline-errors" -ForegroundColor Green

Write-Host "`n  Total: 7 alarms created!" -ForegroundColor Cyan

# ============================================================================
# 4. CLOUDWATCH DASHBOARD
# ============================================================================
Write-Host "`n[4/5] Creating CloudWatch Dashboard..." -ForegroundColor Yellow

$DASHBOARD_BODY = @'
{
  "widgets": [
    {
      "type": "text",
      "x": 0, "y": 0, "width": 24, "height": 1,
      "properties": {
        "markdown": "# NewsRAG Monitoring Dashboard\n*Real-time monitoring for Lambda, RDS Aurora, SQS, and ECS Pipeline*"
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Lambda RAG - Invocations and Errors",
        "metrics": [
          ["AWS/Lambda", "Invocations", "FunctionName", "newsrag-rag-api", {"stat": "Sum", "color": "#2563eb"}],
          ["AWS/Lambda", "Errors", "FunctionName", "newsrag-rag-api", {"stat": "Sum", "color": "#dc2626"}],
          ["AWS/Lambda", "Throttles", "FunctionName", "newsrag-rag-api", {"stat": "Sum", "color": "#f59e0b"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300,
        "stacked": false
      }
    },
    {
      "type": "metric",
      "x": 8, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Lambda ETL - Invocations and Errors",
        "metrics": [
          ["AWS/Lambda", "Invocations", "FunctionName", "newsrag-etl", {"stat": "Sum", "color": "#2563eb"}],
          ["AWS/Lambda", "Errors", "FunctionName", "newsrag-etl", {"stat": "Sum", "color": "#dc2626"}],
          ["AWS/Lambda", "Throttles", "FunctionName", "newsrag-etl", {"stat": "Sum", "color": "#f59e0b"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300,
        "stacked": false
      }
    },
    {
      "type": "metric",
      "x": 16, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Lambda Duration (ms)",
        "metrics": [
          ["AWS/Lambda", "Duration", "FunctionName", "newsrag-rag-api", {"stat": "Average", "color": "#2563eb", "label": "RAG Avg"}],
          ["AWS/Lambda", "Duration", "FunctionName", "newsrag-rag-api", {"stat": "p99", "color": "#dc2626", "label": "RAG p99"}],
          ["AWS/Lambda", "Duration", "FunctionName", "newsrag-etl", {"stat": "Average", "color": "#16a34a", "label": "ETL Avg"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "RDS Aurora - CPU Utilization",
        "metrics": [
          ["AWS/RDS", "CPUUtilization", "DBClusterIdentifier", "newsrag-postgres", {"stat": "Average", "color": "#2563eb"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300,
        "annotations": {
          "horizontal": [{"label": "Warning (80%)", "value": 80, "color": "#dc2626"}]
        }
      }
    },
    {
      "type": "metric",
      "x": 8, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "RDS Aurora - Connections and Memory",
        "metrics": [
          ["AWS/RDS", "DatabaseConnections", "DBClusterIdentifier", "newsrag-postgres", {"stat": "Average", "color": "#8b5cf6"}],
          ["AWS/RDS", "FreeableMemory", "DBClusterIdentifier", "newsrag-postgres", {"stat": "Average", "color": "#16a34a", "yAxis": "right"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300
      }
    },
    {
      "type": "metric",
      "x": 16, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "RDS Aurora - Read/Write Latency",
        "metrics": [
          ["AWS/RDS", "ReadLatency", "DBClusterIdentifier", "newsrag-postgres", {"stat": "Average", "color": "#2563eb", "label": "Read Latency"}],
          ["AWS/RDS", "WriteLatency", "DBClusterIdentifier", "newsrag-postgres", {"stat": "Average", "color": "#dc2626", "label": "Write Latency"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 13, "width": 8, "height": 6,
      "properties": {
        "title": "SQS - Messages Sent and Received",
        "metrics": [
          ["AWS/SQS", "NumberOfMessagesSent", "QueueName", "newsrag-raw-news", {"stat": "Sum", "color": "#2563eb"}],
          ["AWS/SQS", "NumberOfMessagesReceived", "QueueName", "newsrag-raw-news", {"stat": "Sum", "color": "#16a34a"}],
          ["AWS/SQS", "NumberOfMessagesDeleted", "QueueName", "newsrag-raw-news", {"stat": "Sum", "color": "#6b7280"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300
      }
    },
    {
      "type": "metric",
      "x": 8, "y": 13, "width": 8, "height": 6,
      "properties": {
        "title": "SQS DLQ - Dead Letter Queue Depth",
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "newsrag-raw-news-dlq", {"stat": "Sum", "color": "#dc2626", "label": "DLQ Messages"}],
          ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", "newsrag-raw-news-dlq", {"stat": "Maximum", "color": "#f59e0b", "label": "Oldest Message Age (s)", "yAxis": "right"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300,
        "annotations": {
          "horizontal": [{"label": "Alert: Messages in DLQ", "value": 1, "color": "#dc2626"}]
        }
      }
    },
    {
      "type": "metric",
      "x": 16, "y": 13, "width": 8, "height": 6,
      "properties": {
        "title": "Pipeline Custom Metrics",
        "metrics": [
          ["NewsRAG/Pipeline", "PipelineSuccessCount", {"stat": "Sum", "color": "#16a34a", "label": "Success"}],
          ["NewsRAG/Pipeline", "PipelineErrorCount", {"stat": "Sum", "color": "#dc2626", "label": "Errors"}]
        ],
        "view": "timeSeries",
        "region": "ap-southeast-2",
        "period": 300
      }
    },
    {
      "type": "alarm",
      "x": 0, "y": 19, "width": 24, "height": 3,
      "properties": {
        "title": "Alarm Status Overview",
        "alarms": [
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-lambda-rag-errors",
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-lambda-etl-errors",
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-lambda-rag-duration",
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-rds-cpu-high",
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-rds-connections-high",
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-sqs-dlq-not-empty",
          "arn:aws:cloudwatch:ap-southeast-2:814808959551:alarm:newsrag-pipeline-errors"
        ]
      }
    },
    {
      "type": "log",
      "x": 0, "y": 22, "width": 24, "height": 6,
      "properties": {
        "title": "Recent Pipeline Logs",
        "query": "SOURCE '/ecs/newsrag-project' | fields @timestamp, @message | sort @timestamp desc | limit 50",
        "region": "ap-southeast-2",
        "view": "table"
      }
    }
  ]
}
'@

aws cloudwatch put-dashboard `
    --dashboard-name "NewsRAG-Monitor" `
    --dashboard-body $DASHBOARD_BODY `
    --region $REGION

Write-Host "  Dashboard created: NewsRAG-Monitor" -ForegroundColor Green

# ============================================================================
# 5. SUMMARY & OUTPUTS
# ============================================================================
Write-Host "`n[5/5] Setup Complete!" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " SUMMARY" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SNS Topic:     $SNS_ARN"
Write-Host "  Metric Filters: 2 (PipelineErrorCount, PipelineSuccessCount)"
Write-Host "  Alarms:         7"
Write-Host "  Dashboard:      NewsRAG-Monitor"
Write-Host ""
Write-Host "  Dashboard URL:" -ForegroundColor Green
Write-Host "  https://ap-southeast-2.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#dashboards/dashboard/NewsRAG-Monitor" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [!] Don't forget to CONFIRM the SNS email subscription!" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Cyan

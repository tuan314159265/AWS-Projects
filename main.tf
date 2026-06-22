provider "aws" {
  region = "ap-southeast-2"
}

# --- Variables ---
variable "db_password" {
  type      = string
  sensitive = true
}

variable "db_user" {
  type = string
}

variable "db_host" {
  type = string
}

variable "qdrant_api_key" {
  type      = string
  sensitive = true
}

variable "qdrant_host" {
  type = string
}

variable "model_1_api_key" {
  type      = string
  sensitive = true
}

variable "model_2_api_key" {
  type      = string
  sensitive = true
}

variable "model_3_api_key" {
  type      = string
  sensitive = true
}

# --- Environment ---
locals {
  common_env = [
    { name = "DB_NAME", value = "postgres" },
    { name = "DB_USER", value = var.db_user },
    { name = "DB_PASSWORD", value = var.db_password },
    { name = "DB_HOST", value = var.db_host },
    { name = "DB_PORT", value = "5432" },
    { name = "QDRANT_HOST", value = var.qdrant_host },
    { name = "QDRANT_PORT", value = "6333" },
    { name = "QDRANT_API_KEY", value = var.qdrant_api_key },
    { name = "QDRANT_COLLECTION_NAME", value = "news_chunks" },
    { name = "KAFKA_BOOTSTRAP_SERVERS", value = "localhost:9092" },
    { name = "KAFKA_TOPIC_NEWS", value = "news_raw" },
    { name = "EMBEDDING_MODEL", value = "BAAI/bge-small-en-v1.5" },
    { name = "EMBEDDING_SIZE", value = "384" },
    { name = "NUM_MODEL_SUPPORT", value = "3" },
    { name = "MODEL_1_NAME", value = "qwen3-8b-instant" },
    { name = "MODEL_1_MODEL_ID", value = "qwen/qwen3-8b-instant" },
    { name = "MODEL_1_PROVIDER", value = "groq" },
    { name = "MODEL_1_API_KEY", value = var.model_1_api_key },
    { name = "MODEL_2_NAME", value = "llama-3.1-8b-instant" },
    { name = "MODEL_2_MODEL_ID", value = "meta-llama/llama-3.1-8b-instant" },
    { name = "MODEL_2_PROVIDER", value = "groq" },
    { name = "MODEL_2_API_KEY", value = var.model_2_api_key },
    { name = "MODEL_3_NAME", value = "gemini-2.0-flash" },
    { name = "MODEL_3_MODEL_ID", value = "gemini-2.0-flash" },
    { name = "MODEL_3_API_KEY", value = var.model_3_api_key },
    { name = "MODEL_3_PROVIDER", value = "google" }
  ]
}

# --- VPC & Network ---
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "newsrag-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "pub_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "ap-southeast-2a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "pub_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "ap-southeast-2b"
  map_public_ip_on_launch = true
}

resource "aws_route_table" "rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.pub_a.id
  route_table_id = aws_route_table.rt.id
}

resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.pub_b.id
  route_table_id = aws_route_table.rt.id
}

# --- Security Groups ---
resource "aws_security_group" "ecs_sg" {
  name   = "newsrag-ecs-sg"
  vpc_id = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- ECR ---
resource "aws_ecr_repository" "api" { name = "newsrag-api" }

# --- ECS Cluster ---
resource "aws_ecs_cluster" "cluster" { name = "newsrag-cluster" }

# --- IAM Roles ---
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "newsrag-ecs-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "newsrag-ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# --- CloudWatch Logs ---
resource "aws_cloudwatch_log_group" "logs" {
  name              = "/ecs/newsrag-project"
  retention_in_days = 7
}

# --- Task Definitions (Lighter: Fargate Spot friendly) ---

resource "aws_ecs_task_definition" "crawler" {
  family                   = "newsrag-crawler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  container_definitions = jsonencode([{
    name  = "crawler"
    image = "${aws_ecr_repository.api.repository_url}:latest"
    command = ["python", "main.py", "--mode", "crawl"]
    environment = local.common_env
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.logs.name
        "awslogs-region"        = "ap-southeast-2"
        "awslogs-stream-prefix" = "crawler"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "etl" {
  family                   = "newsrag-etl"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  container_definitions = jsonencode([{
    name  = "etl"
    image = "${aws_ecr_repository.api.repository_url}:latest"
    command = ["python", "main.py", "--mode", "etl"]
    environment = local.common_env
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.logs.name
        "awslogs-region"        = "ap-southeast-2"
        "awslogs-stream-prefix" = "etl"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "vectorize" {
  family                   = "newsrag-vectorize"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  container_definitions = jsonencode([{
    name  = "vectorize"
    image = "${aws_ecr_repository.api.repository_url}:latest"
    command = ["python", "main.py", "--mode", "vectorize"]
    environment = local.common_env
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.logs.name
        "awslogs-region"        = "ap-southeast-2"
        "awslogs-stream-prefix" = "vectorize"
      }
    }
  }])
}

# --- Scheduled Tasks (EventBridge) ---

resource "aws_cloudwatch_event_rule" "crawler_schedule" {
  name                = "newsrag-crawler-rule"
  schedule_expression = "cron(0 1 * * ? *)"
}

resource "aws_cloudwatch_event_target" "crawler_target" {
  rule      = aws_cloudwatch_event_rule.crawler_schedule.name
  arn       = aws_ecs_cluster.cluster.arn
  role_arn  = aws_iam_role.ecs_task_execution_role.arn
  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.crawler.arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = [aws_subnet.pub_a.id, aws_subnet.pub_b.id]
      security_groups  = [aws_security_group.ecs_sg.id]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_rule" "etl_schedule" {
  name                = "newsrag-etl-rule"
  schedule_expression = "cron(0 2 * * ? *)"
}

resource "aws_cloudwatch_event_target" "etl_target" {
  rule      = aws_cloudwatch_event_rule.etl_schedule.name
  arn       = aws_ecs_cluster.cluster.arn
  role_arn  = aws_iam_role.ecs_task_execution_role.arn
  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.etl.arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = [aws_subnet.pub_a.id, aws_subnet.pub_b.id]
      security_groups  = [aws_security_group.ecs_sg.id]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_rule" "vectorize_schedule" {
  name                = "newsrag-vectorize-rule"
  schedule_expression = "cron(0 3 * * ? *)"
}

resource "aws_cloudwatch_event_target" "vectorize_target" {
  rule      = aws_cloudwatch_event_rule.vectorize_schedule.name
  arn       = aws_ecs_cluster.cluster.arn
  role_arn  = aws_iam_role.ecs_task_execution_role.arn
  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.vectorize.arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = [aws_subnet.pub_a.id, aws_subnet.pub_b.id]
      security_groups  = [aws_security_group.ecs_sg.id]
      assign_public_ip = true
    }
  }
}

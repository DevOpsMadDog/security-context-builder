# Pattern1 reference Terraform. Sandbox only; review before any apply.
# Prerequisites: existing VPC, ALB public subnets in two AZs, private ECS
# subnets with ECR/CloudWatch connectivity, issued ACM certificate and a
# pre-created ECR repository. Backend settings supplied by Azure Pipelines.
terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 7.0"
    }
  }
  backend "s3" {}
}

variable "aws_region" { type = string }
variable "app_name" {
  type = string
  default = "vulnapp"
}
variable "environment" {
  type = string
  default = "sandbox"
}
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "certificate_arn" { type = string }
variable "ecr_repository_name" {
  type = string
  default = "vulnapp"
}
variable "image_uri" {
  type = string
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image_uri))
    error_message = "Use a fully qualified immutable ECR image URI with a sha256 digest."
  }
}
provider "aws" { region = var.aws_region }
data "aws_caller_identity" "current" {}
data "aws_ecr_repository" "app" { name = var.ecr_repository_name }

locals { name = "${var.app_name}-${var.environment}" }

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = 30
}

resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  description = "Pattern1: internet-facing HTTPS ALB"
  vpc_id      = var.vpc_id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "task" {
  name_prefix = "${local.name}-task-"
  description = "Pattern1: private Fargate tasks, ALB traffic only"
  vpc_id      = var.vpc_id
  # Example intentionally broad HTTPS egress, review and restrict with endpoints.
  # Synthetic Prisma fixture flags this egress for a Terraform PR.
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "alb_to_task" {
  type                     = "egress"
  from_port                = 3000
  to_port                  = 3000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.alb.id
  source_security_group_id = aws_security_group.task.id
}

resource "aws_security_group_rule" "task_from_alb" {
  type                     = "ingress"
  from_port                = 3000
  to_port                  = 3000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.task.id
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_lb" "app" {
  name                       = local.name
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.public_subnet_ids
  enable_deletion_protection = false # sandbox only
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "app" {
  name        = "${local.name}-tg"
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path                = "/health"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_wafv2_web_acl" "app" {
  name  = "${local.name}-waf"
  scope = "REGIONAL"
  default_action { allow {} }
  rule {
    name     = "AWSManagedCommonRuleSet"
    priority = 1
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "pattern1-common-rules"
      sampled_requests_enabled   = true
    }
  }
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "pattern1-waf"
    sampled_requests_enabled   = true
  }
}
resource "aws_wafv2_web_acl_association" "app" {
  resource_arn = aws_lb.app.arn
  web_acl_arn  = aws_wafv2_web_acl.app.arn
}

resource "aws_iam_role" "execution" {
  name = "${local.name}-ecs-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role" "task" {
  name = "${local.name}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  # No application AWS privileges in this reference example.
}

resource "aws_ecs_cluster" "app" { name = local.name }
resource "aws_ecs_task_definition" "app" {
  family                   = local.name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name      = "api"
    image     = var.image_uri
    essential = true
    portMappings = [{ containerPort = 3000, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}
resource "aws_ecs_service" "app" {
  name                               = local.name
  cluster                            = aws_ecs_cluster.app.id
  launch_type                        = "FARGATE"
  desired_count                      = 2
  task_definition                    = aws_ecs_task_definition.app.arn
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "api"
    container_port   = 3000
  }
  depends_on = [aws_lb_listener.https, aws_wafv2_web_acl_association.app, aws_iam_role_policy_attachment.execution, aws_security_group_rule.task_from_alb, aws_security_group_rule.alb_to_task]
}

output "aws_region" { value = var.aws_region }
output "aws_account_id" { value = data.aws_caller_identity.current.account_id }
output "ecs_cluster_name" { value = aws_ecs_cluster.app.name }
output "ecs_service_name" { value = aws_ecs_service.app.name }
output "ecs_service_arn" { value = aws_ecs_service.app.id }
output "ecs_task_definition_arn" { value = aws_ecs_task_definition.app.arn }
output "alb_arn" { value = aws_lb.app.arn }
output "waf_web_acl_arn" { value = aws_wafv2_web_acl.app.arn }
output "ecr_repository_url" { value = data.aws_ecr_repository.app.repository_url }

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  current_account_id = data.aws_caller_identity.current.account_id
  current_region     = data.aws_region.current.name
}

data "aws_kms_alias" "this" {
  name = var.kms_alias_id
}

resource "aws_ssm_parameter" "this" {
  name   = "/${var.name_prefix}/rmapi-config"
  type   = "SecureString"
  value  = "{}"
  key_id = data.aws_kms_alias.this.arn
  tags   = var.tags
  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_lambda_function" "this" {
  function_name = "${var.name_prefix}-paper2remarkable"
  role          = aws_iam_role.this.arn
  image_uri     = var.lambda_image_uri
  memory_size   = var.lambda_memory_size
  package_type  = "Image"
  environment {
    variables = {
      SSM_PARAMETER_NAME = aws_ssm_parameter.this.name
    }
  }
  timeout = var.lambda_timeout
  tags    = var.tags
}

resource "aws_lambda_function_event_invoke_config" "this" {
  function_name          = aws_lambda_function.this.function_name
  maximum_retry_attempts = 0
}

resource "aws_iam_role" "this" {
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "logs_to_lambda" {
  policy = data.aws_iam_policy_document.logs_for_lambda.json
  role   = aws_iam_role.this.id
}

resource "aws_iam_role_policy" "kms_to_lambda" {
  policy = data.aws_iam_policy_document.kms_for_lambda.json
  role   = aws_iam_role.this.id
}

resource "aws_iam_role_policy" "ssm_to_lambda" {
  policy = data.aws_iam_policy_document.ssm_for_lambda.json
  role   = aws_iam_role.this.id
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${aws_lambda_function.this.function_name}"
  retention_in_days = 14
  tags              = var.tags
}

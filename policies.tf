data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }
  }
}

data "aws_iam_policy_document" "logs_for_lambda" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:${local.current_region}:${local.current_account_id}:log-group:/aws/lambda/${aws_lambda_function.this.function_name}:*",
    ]
  }
}

data "aws_iam_policy_document" "kms_for_lambda" {
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [data.aws_kms_alias.this.target_key_arn]
  }
}

data "aws_iam_policy_document" "ssm_for_lambda" {
  statement {
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.this.arn]
  }
}

data "aws_iam_policy_document" "sns_for_lambda" {
  count = var.failure_notification_email != "" ? 1 : 0
  statement {
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.this[0].arn]
  }
}

output "lambda_invoke_arn" {
  value = aws_lambda_function.this.invoke_arn
}

output "lambda_function_name" {
  value = aws_lambda_function.this.function_name
}

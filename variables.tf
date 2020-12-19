variable "name_prefix" {
  description = "A prefix used for naming resources."
  type        = string
}

variable "lambda_image_uri" {
  description = "URI of a container image in ECR."
  type        = string
}

variable "lambda_timeout" {
  description = "The maximum number of seconds the Lambda is allowed to run."
  default     = 180
}

variable "lambda_memory_size" {
  description = "Amounts of memory allocated to the Lambda."
  default     = 256
}

variable "tags" {
  description = "A map of tags (key-value pairs) passed to resources."
  type        = map(string)
  default     = {}
}

variable "kms_alias_id" {
  description = "The ID of a KMS alias to use when encrypting SSM parameters."
  type        = string
}

variable "failure_notification_email" {
  description = "An optional email to send notifications to if paper2remarkable fails to process one or more inputs."
  default     = ""
}

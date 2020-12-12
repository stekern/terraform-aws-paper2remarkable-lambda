data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix        = "example"
  current_account_id = data.aws_caller_identity.current.account_id
  current_region     = data.aws_region.current.name
}

resource "aws_kms_key" "main" {}
resource "aws_kms_alias" "main" {
  name          = "alias/${local.name_prefix}-main"
  target_key_id = aws_kms_key.main.id
}

module "paper2remarkable" {
  source           = "../../"
  name_prefix      = local.name_prefix
  kms_alias_id     = aws_kms_alias.main.id
  lambda_image_uri = "<ecr-image-uri>"
}

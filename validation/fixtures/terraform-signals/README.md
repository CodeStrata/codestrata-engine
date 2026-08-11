# terraform-signals (controlled fixture)

Static Terraform IaC stub for Epic 4 Slice 4.13 cloud/IaC validation.

## Intentional positives

| Path | Signal | Notes |
|------|--------|-------|
| `main.tf` | IaC / AWS provider | `aws_s3_bucket` and `aws_lambda_function` resource blocks only |

## Safety

- No credentials, access keys, or remote state backends
- HCL resource stubs only; do not run `terraform apply`
- CodeStrata-owned validation fixture; not a customer example

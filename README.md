# terraform-provider-cloudtamerio

The Terraform provider for cloudtamer.io allows you interact with the cloudtamer.io API using the Terraform HCL language. Our provider supports creating, updating, reading, and deleting resources. You can also use it to query for resources using filters even if a resource is not created through Terraform.

- [terraform-provider-cloudtamerio](#terraform-provider-cloudtamerio)
  - [Getting Started](#getting-started)
    - [Importing Resource State](#importing-resource-state)
  - [Sample Commands](#sample-commands)
    - [Resources](#resources)
    - [Data Sources](#data-sources)
    - [Locals](#locals)

## Getting Started

Below is sample code on how to create an IAM policy in cloudtamer.io using Terraform.

First, set your environment variables:

```bash
export CLOUDTAMERIO_URL=https://cloudtamerio.example.com
export CLOUDTAMERIO_APIKEY=API-KEY-HERE
```

Next, paste this code into a `main.tf` file:

```hcl
terraform {
  required_providers {
    cloudtamerio = {
      source  = "cloudtamer-io/cloudtamerio"
      version = "0.1.5"
    }
  }
}

provider "cloudtamerio" {
  # If these are commented out, they will be loaded from environment variables.
  # url = "https://cloudtamerio.example.com"
  # apikey = "key here"
}

# Create an IAM policy.
resource "cloudtamerio_aws_iam_policy" "p1" {
  name         = "sample-resource"
  description  = "Provides read only access to Amazon EC2 via the AWS Management Console."
  aws_iam_path = ""
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "*",
            "Resource": "*"
        }
    ]
}
EOF
}

# Output the ID of the resource created.
output "policy_id" {
  value = cloudtamerio_aws_iam_policy.p1.id
}
```

Then, run these commands:

```bash
# Initialize the project.
terraform init

# Show the plan.
terraform plan

# Apply the changes.
terraform apply --auto-approve
```

You can now make changes to the `main.tf` file and then re-run the `apply` command to push the changes to cloudtamer.io.

### Importing Resource State

This provider does support [importing state for resources](https://www.terraform.io/docs/cli/import/index.html). You will need to create the Terraform files and then you can run commands like this to generate the `terraform.tfstate` so you don't have to delete all your resources and then recreate them to work with Terraform:

```bash
# Initialize the project.
terraform init

# Import the resource from your environment - this assumes you have a module called
# 'aws-cloudformation-template' and you are importing into a resource you defined as 'AuditLogging'.
# The '20' at the end is the ID of the resource in cloudtamer.io.
terraform import module.aws-cloudformation-template.cloudtamerio_aws_cloudformation_template.AuditLogging 20

# Verify the state is correct - there shouldn't be any changes listed.
terraform plan
```

## Sample Commands

Below is a collection of sample commands when working with the Terraform provider.

### Resources

A few of the optional fields are commented out.

```hcl
# Create an IAM policy.
resource "cloudtamerio_aws_iam_policy" "p1" {
  name = "sample-resource"
  # description  = "Provides read only access to Amazon EC2 via the AWS Management Console."
  # aws_iam_path = ""
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "*",
            "Resource": "*"
        }
    ]
}
EOF
}

# Output the ID of the resource created.
output "policy_id" {
  value = cloudtamerio_aws_iam_policy.p1.id
}
```

```hcl
# Create a CloudFormation template.
resource "cloudtamerio_aws_cloudformation_template" "t1" {
  name    = "sample-resource"
  regions = ["us-east-1"]
  # description = "Creates a test IAM role."
  # region                 = ""
  # sns_arns               = ""
  # template_parameters    = ""
  # termination_protection = false
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
  policy = <<EOF
{
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "Creates a test IAM role.",
    "Metadata": {
        "VersionDate": {
            "Value": "20180718"
        },
        "Identifier": {
            "Value": "blank-role.json"
        }
    },
    "Resources": {
        "EnvTestRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "RoleName": "env-test-role",
                "Path": "/",
                "Policies": [],
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": [
                                    "ec2.amazonaws.com"
                                ]
                            },
                            "Action": [
                                "sts:AssumeRole"
                            ]
                        }
                    ]
                }
            }
        }
    }
}
EOF
}

# Output the ID of the resource created.
output "template_id" {
  value = cloudtamerio_aws_cloudformation_template.t1.id
}
```

```hcl
# Create an external compliance check.
resource "cloudtamerio_compliance_check" "c1" {
  name                     = "sample-resource"
  created_by_user_id       = 1
  cloud_provider_id        = 1
  compliance_check_type_id = 1
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
  #   body = <<EOF
  # {
  #     "Version": "2012-10-17",
  #     "Statement": [
  #         {
  #             "Effect": "Allow",
  #             "Action": "*",
  #             "Resource": "*"
  #         }
  #     ]
  # }
  # EOF
}

# Output the ID of the resource created.
output "check_id" {
  value = cloudtamerio_compliance_check.c1.id
}
```

```hcl
# Create a compliance standard.
resource "cloudtamerio_compliance_standard" "s1" {
  name               = "sample-resource"
  created_by_user_id = 1
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
}

# Output the ID of the resource created.
output "standard_id" {
  value = cloudtamerio_compliance_standard.s1.id
}
```

```hcl
# Create a cloud rule.
resource "cloudtamerio_cloud_rule" "cr1" {
  name        = "sample-resource"
  description = "Sample cloud rule."
  aws_iam_policies { id = 1 }
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
}

# Output the ID of the resource created.
output "rule_id" {
  value = cloudtamerio_cloud_rule.cr1.id
}
```

```hcl
# Create a cloud access role on a project.
resource "cloudtamerio_project_cloud_access_role" "carp1" {
  name                   = "sample-car"
  project_id             = 1
  aws_iam_role_name      = "sample-car"
  web_access             = true
  short_term_access_keys = true
  long_term_access_keys  = true
  aws_iam_policies { id = 1 }
  aws_iam_permissions_boundary = 1
  future_accounts              = true
  #accounts { id = 1 }
  users { id = 1 }
  user_groups { id = 1 }
}

# Output the ID of the resource created.
output "project_car_id" {
  value = cloudtamerio_project_cloud_access_role.carp1.id
}
```

```hcl
# Create a cloud access role on an OU.
resource "cloudtamerio_ou_cloud_access_role" "carou1" {
  name                   = "sample-car"
  ou_id                  = 3
  aws_iam_role_name      = "sample-car"
  web_access             = true
  short_term_access_keys = true
  long_term_access_keys  = true
  aws_iam_policies { id = 628 }
  #aws_iam_permissions_boundary = 1
  users { id = 1 }
  user_groups { id = 1 }
}

# Output the ID of the resource created.
output "ou_car_id" {
  value = cloudtamerio_ou_cloud_access_role.carou1.id
}
```

```hcl
# Create an OU.
resource "cloudtamerio_ou" "ou1" {
  name         = "sample-ou"
  description  = "Sample OU."
  parent_ou_id = 0
  permission_scheme_id = 2
  owner_users { id = 1 }
  owner_user_groups { id = 1 }
}

# Output the ID of the resource created.
output "ou_id" {
  value = cloudtamerio_ou.ou1.id
}
```

### Data Sources

```hcl
# Declare a data source to get all IAM policies.
data "cloudtamerio_aws_iam_policy" "p1" {}

# Output the list of all policies.
output "policies" {
  value = data.cloudtamerio_aws_iam_policy.p1.list
}

# Output the first policy (which by default is the newest policy).
output "first" {
  value = data.cloudtamerio_aws_iam_policy.p1.list[0]
}

# Output the first policy name.
output "policy_name" {
  value = data.cloudtamerio_aws_iam_policy.p1.list[0].name
}

# Output a list of all policy names.
output "policy_names" {
  value = data.cloudtamerio_aws_iam_policy.p1.list.*.name
}

# Output a list of all owner users for all policies.
output "policy_owner_users" {
  value = data.cloudtamerio_aws_iam_policy.p1.list.*.owner_users
}
```

```hcl
# Declare a data source to get 1 IAM policy that matches the name filter.
data "cloudtamerio_aws_iam_policy" "p1" {
  filter {
    name   = "name"
    values = ["SystemReadOnlyAccess"]
  }
}

# Declare a data source to get 2 IAM policies that matches the name filter.
data "cloudtamerio_aws_iam_policy" "p1" {
  filter {
    name   = "name"
    values = ["SystemReadOnlyAccess", "test-policy"]
  }
}

# Declare a data source to get 1 IAM policy that matches both of the filters.
# SystemReadOnlyAccess has the id of 1 so only that policy matches all of the filters.
data "cloudtamerio_aws_iam_policy" "p1" {
  filter {
    name   = "name"
    values = ["SystemReadOnlyAccess", "test-policy"]
  }

  filter {
    name   = "id"
    values = [1]
  }
}

# Declare a data source to get all IAM policies that matches the owner filter.
# Syntax to filter on an array.
data "cloudtamerio_aws_iam_policy" "p1" {
  filter {
    name   = "owner_users.id"
    values = ["20"]
  }
}

# Declare a data source to get all IAM policies that matches the id filter.
# Notice that terraform will convert these to strings even though you
# passed in an integer.
data "cloudtamerio_aws_iam_policy" "p1" {
  filter {
    name = "id"
    values = [1, "3"]
    # Terraform will convert all of these to strings.
    # + values = [
    #     + "1",
    #     + "3",
    #   ]
  }
}

# Declare a data source to get all IAM policies that matches the query.
output "policy_access" {
  value = {
    # Loop through each policy
    for c in data.cloudtamerio_aws_iam_policy.p1.list :
    # Create a map with a key of: id
    c.id => c
    # Filter out an names that don't match the passed in variable
    if c.name == "SystemReadOnlyAccess"
  }
}
```

### Locals

```hcl
# Declare a data source to get all IAM policies.
data "cloudtamerio_aws_iam_policy" "p1" {}

# Declare a local variable: local.owners
locals {
  # Owners for multiple policies merged together.
  owners = concat(data.cloudtamerio_aws_iam_policy.p1.list[0].owner_users, data.cloudtamerio_aws_iam_policy.p1.list[1].owner_users)
}

# Output the local variable.
output "policy_owner_users" {
  value = local.owners
}
```

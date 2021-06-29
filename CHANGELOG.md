# Changelog

All notable changes to this project will be documented in this file.

## [0.1.3] - 2021-06-29
### Changed
- Fix bug on project cloud access role creation so 'apply_to_all_accounts' and 'accounts' fields are mutually exclusive.
- Remove unused errors throughout the code.

## [0.1.2] - 2021-04-01
### Added
- Support creating, updating, and deleting resources for: OU cloud access roles and project cloud access roles.

## Changed
- Fix bug on compliance standard creation so compliance checks are attached during creation instead of requiring another `terraform apply`.
- Fix bug on cloud rule creation so associated items are attached during creation instead of requiring another `terraform apply`.

## [0.1.1] - 2021-03-30
### Added
- Ability to import resources using `terraform import`.

## [0.1.0] - 2021-02-08
### Added
- Initial release of the provider.
- Support creating, updating, and deleting resources for: AWS CloudFormation templates, AWS IAM policies, Azure policies, cloud rules, compliance checks, and compliance standards.
- Support querying data sources for: AWS CloudFormation templates, AWS IAM policies, Azure policies, cloud rules, compliance checks, and compliance standards.
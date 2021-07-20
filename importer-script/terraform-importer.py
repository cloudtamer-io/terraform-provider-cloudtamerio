"""
cloudtamer.io Terraform Provider Importer

This script imports existing cloud resources into a source control repository
for management by the Terraform Provider.

See the README for usage and optional flags.
"""

import os
import re
import sys
import json
import textwrap
import argparse
import requests
from json.decoder import JSONDecodeError

PARSER = argparse.ArgumentParser(description='Import Cloud Resources into the Repo Module')
PARSER.add_argument('--ct-url', type=str, required=True, help='URL to cloudtamer, without trailing slash. Example: https://cloudtamer.myorg.com')
PARSER.add_argument('--ct-api-key', type=str, help='cloudtamer API key. Can be set via env variable CLOUDTAMERIO_APIKEY or CT_API_KEY instead (preferred).')
PARSER.add_argument('--import-dir', type=str, required=True, help='Path to the root of the target import directory, without trailing slash.')
PARSER.add_argument('--skip-cfts', action='store_true', help='Skip importing AWS CloudFormation templates.')
PARSER.add_argument('--skip-iams', action='store_true', help='Skip importing AWS IAM policies.')
PARSER.add_argument('--skip-project-roles', action='store_true', help='Skip importing Project Cloud Access Roles.')
PARSER.add_argument('--skip-ou-roles', action='store_true', help='Skip importing OU Cloud Access Roles.')
PARSER.add_argument('--skip-cloud-rules', action='store_true', help='Skip importing Cloud Rules.')
PARSER.add_argument('--skip-checks', action='store_true', help='Skip importing Compliance Checks.')
PARSER.add_argument('--skip-standards', action='store_true', help='Skip importing Compliance Standards.')
PARSER.add_argument('--skip-ssl-verify', action='store_true',help='Skip SSL verification. Use if cloudtamer.io does not have a valid SSL certificate.')
PARSER.add_argument('--overwrite', action='store_true',help='Overwrite existing files during import.')
PARSER.add_argument('--prepend-id', action='store_true',help='Prepend each resource\'s ID to its filenames. Useful for easily correlating IDs to resources')
# PARSER.add_argument('--dry-run', action='store_true', help='Perform a dry run without writing any files.')
# PARSER.add_argument('--sync', action='store_true',help='Sync repository resources into cloudtamer.')
ARGS = PARSER.parse_args()

# validate ct_url
if not ARGS.ct_url:
    sys.exit("Please provide the URL to cloudtamer. Example: --ct-url https://cloudtamer.myorg.com")
# remove trailing slash if found
elif re.compile(".+/$").match(ARGS.ct_url):
    ARGS.ct_url = re.sub(r'/$', '', ARGS.ct_url)

# validate import_dir
if not ARGS.import_dir:
    sys.exit("Please provide the path to the directory in which to import. Example: --import-dir /Users/me/code/repo-module-dir")
# remove trailing slash if found
elif re.compile(".+/$").match(ARGS.import_dir):
    ARGS.import_dir = re.sub(r'/$', '', ARGS.import_dir)

# validate API key
if not ARGS.ct_api_key:
    if os.environ.get('CLOUDTAMERIO_APIKEY'):
        ARGS.ct_api_key = os.environ['CLOUDTAMERIO_APIKEY']
    elif os.environ.get('CT_API_KEY'):
        ARGS.ct_api_key = os.environ['CT_API_KEY']
    else:
        sys.exit("Did not find a cloudtamer API key supplied via CLI argument or environment variable (CLOUDTAMERIO_APIKEY or CT_API_KEY).")

BASE_URL = "%s/api" % ARGS.ct_url
HEADERS = {"accept": "application/json", "Authorization": "Bearer " + ARGS.ct_api_key}

MAX_UNAUTH_RETRIES = 15
UNAUTH_RETRY_COUNTER = 0

RESOURCE_PREFIX     = 'cloudtamerio'
IMPORTED_MODULES    = []
IMPORTED_RESOURCES  = []

PROVIDER_TEMPLATE = textwrap.dedent('''\
    terraform {
        required_providers {
            cloudtamerio = {
                source  = "cloudtamer-io/cloudtamerio"
                version = "0.1.3"
            }
        }
    }

    provider "cloudtamerio" {
        # Configuration options
    }
    ''')

MAIN_PROVIDER_TEMPLATE = textwrap.dedent('''\

    module "aws-cloudformation-template" {
        source = "./aws-cloudformation-template"
    }

    module "aws-iam-policy" {
        source = "./aws-iam-policy"
    }

    module "cloud-rule" {
        source = "./cloud-rule"
    }

    module "compliance-check" {
        source = "./compliance-check"
    }

    module "compliance-standard" {
        source = "./compliance-standard"
    }
    ''')

OWNERS_TEMPLATE = textwrap.dedent('''\
    {owner_users}
    ''')

OWNER_GROUPS_TEMPLATE = textwrap.dedent('''\
    {owner_user_groups}
    ''')

OUTPUT_TEMPLATE = textwrap.dedent('''\
    output "{resource_id}" {{
        value = {resource_type}.{resource_id}.id
    }}''')

def main():
    """
    Main Function

    All processing occurs here.
    """

    # Run some validations prior to starting
    validate_connection(ARGS.ct_url)
    validate_import_dir(ARGS.import_dir)

    # if ARGS.sync:
    #     sync(ARGS)
    #     sys.exit()

    print("\nBeginning import from %s" % ARGS.ct_url)

    if not ARGS.skip_cfts:
        import_cfts()
    else:
        print("\nSkipping AWS CloudFormation Templates")

    if not ARGS.skip_iams:
        import_iams()
    else:
        print("\nSkipping AWS IAM Policies")

    if not ARGS.skip_project_roles:
        import_project_roles()
    else:
        print("\nSkipping Project Cloud Access Roles")

    if not ARGS.skip_ou_roles:
        import_ou_roles()
    else:
        print("\nSkipping OU Cloud Access Roles")

    if not ARGS.skip_cloud_rules:
        import_cloud_rules()
    else:
        print("\nSkipping Cloud Rules")

    if not ARGS.skip_checks:
        import_compliance_checks()
    else:
        print("\nSkipping Compliance Checks")

    if not ARGS.skip_standards:
        import_compliance_standards()
    else:
        print("\nSkipping Compliance Standards")

    # now out of the loop, write the main provider.tf file
    # to pull in the modules
    provider_filename = "%s/main.tf" % ARGS.import_dir
    content = PROVIDER_TEMPLATE

    # loop over all the modules that were imported and
    # add those to main.tf
    for module in IMPORTED_MODULES:
        module_template = textwrap.dedent('''\

            module "{module_name}" {{
                source = "./{module_name}"
            }}
            ''')

        module_content = module_template.format(
            module_name=module
        )
        content += module_content

    write_provider_file(provider_filename, content)
    write_resource_import_script(ARGS, IMPORTED_RESOURCES)
    print("\nIf you need to refresh the terraform state of the imported resources, run:\n")
    print("cd %s ; bash import_resource_state.sh" % ARGS.import_dir)
    print("\nImport finished.")
    sys.exit()


def import_cfts():
    """
    Import CloudFormation Templates

    Handles full process to import CFTs

    Returns:
        success - True
        failure - False
    """
    CFTs = get_objects_or_ids('aws_cloudformation_templates')

    if CFTs:
        print("\nImporting AWS CloudFormation Templates\n--------------------------")
        print("Found %s CFTs" % len(CFTs))
        IMPORTED_MODULES.append("aws-cloudformation-template")

        for c in CFTs:

            # init new cft object
            cft = {}
            c_id = c['cft']['id']
            cft['name'] = process_string(c['cft']['name'])
            cft['description'] = process_string(c['cft']['description'])
            cft['regions'] = json.dumps(c['cft']['regions'])
            cft['region'] = c['cft']['region']
            cft['sns_arns'] = process_string(c['cft']['sns_arns'])
            cft['template_parameters'] = c['cft']['template_parameters'].rstrip()
            cft['termination_protection'] = c['cft']['termination_protection']
            cft['owner_user_ids'] = []
            cft['owner_user_group_ids'] = []
            cft['policy'] = c['cft']['policy'].rstrip()

            print("Importing CFT - %s" % cft['name'])

            # get owner user and group IDs formatted into required format
            owner_users     = process_owners(c['owner_users'], 'owner_users')
            owner_groups    = process_owners(c['owner_user_groups'], 'owner_user_groups')

            # need to figure out if the template is json or yaml
            # cft_format = ''
            # try:
            #     json.loads(cft['policy'])
            # except:
            #     cft_format = "yaml"
            # else:
            #     cft_format = "json"

            # pre-process some of the data to fit the required format
            cft['sns_params'] = '\n'.join(cft['sns_arns'])

            # double all single dollar signs to be valid for TF format
            cft['policy'] = re.sub(r'\${1}\{', r'$${', cft['policy'])

            if not cft['region']:
                cft['region'] = 'null'

            template = textwrap.dedent('''\
                resource "{resource_type}" "{resource_id}" {{
                    # id                      = {id}
                    name                    = "{resource_name}"
                    description             = "{description}"
                    regions                 = {regions}
                    region                  = "{region}"
                    sns_arns                = "{sns_arns}"
                    termination_protection  = {termination_protection}
                    {owner_users}
                    {owner_groups}

                    template_parameters = <<-EOT
                {template_params}
                EOT

                    policy = <<-EOT
                {policy}
                EOT
                }}

                output "{resource_id}" {{
                    value = {resource_type}.{resource_id}.id
                }}''')

            content = template.format(
                resource_type="%s_aws_cloudformation_template" % RESOURCE_PREFIX,
                resource_id=normalize_string(cft['name']),
                id=c_id,
                resource_name=cft['name'],
                description=cft['description'],
                regions=cft['regions'],
                region=cft['region'],
                sns_arns=cft['sns_arns'],
                termination_protection=str(cft['termination_protection']).lower(),
                owner_users='\n    '.join(owner_users),
                owner_groups='\n    '.join(owner_groups),
                template_params=cft['template_parameters'],
                policy=cft['policy']
            )

            # do some post-processing of the rendered template prior to 
            # writing it out
            if not c['cft']['template_parameters']:
                content = re.sub('\s*template_parameters = <<-EOT\n\nEOT', '', content)

            if cft['region'] == "null":
                content = re.sub('\s*region\s*= "null"', '', content)

            # build the file name
            if ARGS.prepend_id:
                base_filename = normalize_string(cft['name'], c_id)
            else:
                base_filename = normalize_string(cft['name'])

            filename = "%s/aws-cloudformation-template/%s.tf" % (ARGS.import_dir, base_filename)

            write_file(filename, process_template(content))

            # add to IMPORTED_RESOURCES
            resource = "module.aws-cloudformation-template.%s_aws_cloudformation_template.%s %s" % (RESOURCE_PREFIX, normalize_string(cft['name']), c_id)
            IMPORTED_RESOURCES.append(resource)

        # now out of the loop, write the provider.tf file
        provider_filename = "%s/aws-cloudformation-template/provider.tf" % ARGS.import_dir
        write_provider_file(provider_filename, PROVIDER_TEMPLATE)

        print("Done.")
        return True
    else:
        print("Error while importing CFTs.")
        return False


def import_iams():
    """
    Import IAM Policies

    Handles full process to import IAM Policies

    Returns:
        success - True
        failure - False
    """
    IAMs = get_objects_or_ids('aws_iam_policies')

    if IAMs:
        print("\nImporting AWS IAM Policies\n--------------------------")
        print("Found %s IAM Policies" % len(IAMs))
        IMPORTED_MODULES.append("aws-iam-policy")

        for i in IAMs:

            if i['iam_policy']['aws_managed_policy']:
                print("Skipping AWS-managed IAM Policy: %s" % i['iam_policy']['name'])
                continue

            if i['iam_policy']['system_managed_policy']:
                print("Skipping System-managed IAM Policy: %s" % i['iam_policy']['name'])
                continue

            # init new IAM object
            iam = {}
            i_id = i['iam_policy']['id']
            iam['name'] = process_string(i['iam_policy']['name'])
            iam['description'] = process_string(i['iam_policy']['description'])
            iam['owner_user_ids'] = []
            iam['owner_user_group_ids'] = []
            iam['policy'] = i['iam_policy']['policy'].rstrip()

            print("Importing IAM Policy - %s" % iam['name'])

            # check for IAM path - requires cloudtamer > 2.23
            if 'aws_iam_path' in i:
                iam['aws_iam_path'] = i['aws_iam_path'].strip()
            else:
                iam['aws_iam_path'] = ''

            # double all single dollar signs to be valid for TF format
            iam['policy'] = re.sub(r'\${1}\{', r'$${', iam['policy'])

            # get owner user and group IDs formatted into required format
            owner_users     = process_owners(i['owner_users'], 'owner_users')
            owner_groups    = process_owners(i['owner_user_groups'], 'owner_user_groups')

            template = textwrap.dedent('''\
                resource "{resource_type}" "{resource_id}" {{
                    # id              = {id}
                    name            = "{resource_name}"
                    description     = "{description}"
                    aws_iam_path    = "{aws_iam_path}"
                    {owner_users}
                    {owner_groups}
                    policy = <<-EOT
                {policy}
                EOT

                }}

                output "{resource_id}" {{
                    value = {resource_type}.{resource_id}.id
                }}''')

            content = template.format(
                resource_type="%s_aws_iam_policy" % RESOURCE_PREFIX,
                resource_id=normalize_string(iam['name']),
                id=i_id,
                resource_name=iam['name'],
                description=iam['description'],
                aws_iam_path=iam['aws_iam_path'],
                owner_users='\n    '.join(owner_users),
                owner_groups='\n    '.join(owner_groups),
                policy=iam['policy']
            )

            # build the file name
            if ARGS.prepend_id:
                base_filename = normalize_string(iam['name'], i_id)
            else:
                base_filename = normalize_string(iam['name'])

            filename = "%s/aws-iam-policy/%s.tf" % (ARGS.import_dir, base_filename)

            write_file(filename, process_template(content))

            # add to IMPORTED_RESOURCES
            resource = "module.aws-iam-policy.%s_aws_iam_policy.%s %s" % (RESOURCE_PREFIX, normalize_string(iam['name']), i_id)
            IMPORTED_RESOURCES.append(resource)

        # now out of the loop, write the provider.tf file
        provider_filename = "%s/aws-iam-policy/provider.tf" % ARGS.import_dir
        write_provider_file(provider_filename, PROVIDER_TEMPLATE)

        print("Done.")
        return True
    else:
        print("Error while importing IAM policies.")
        return False


def import_project_roles():
    """
    Import Project Cloud Access Roles

    Handles full process to import Project Cloud Access Roles

    Returns:
        success - True
    """
    print("\nImporting Project Cloud Access Roles\n--------------------------")

    base_path = ARGS.import_dir + "/project-cloud-access-role/"

    # first we need a list of all projects in cloudtamer
    all_projects = get_projects()

    if all_projects:
        IMPORTED_MODULES.append("project-cloud-access-role")

        incomplete_projs = []

        for proj in all_projects:
            proj_id = proj['id']

            # get the normalized name for this project
            proj_name = normalize_string(proj['name'])

            # create the directory name for this project
            # it will be of the format {ID}-{normalized_name}
            # Ex: 13-Test_Project
            proj_dir = "%s-%s" % (str(proj_id), proj_name)

            # get the list of roles for this project
            url = "%s/v3/project/%s/project-cloud-access-role" % (BASE_URL, proj_id)
            roles = api_call(url)

            if roles:
                print("Found %s roles on Project (ID: %s) %s" % (len(roles), proj_id, proj['name']))

                # create a folder for this project to keep all roles together
                if not os.path.isdir(base_path+proj_dir):
                    os.mkdir(base_path+proj_dir)

                for r in roles:
                    # pull out the id for this role
                    r_id = r['id']

                    # init new role object
                    role = {}
                    role['name'] = r['name']
                    role['aws_iam_role_name'] = r['aws_iam_role_name']
                    role['project_id'] = proj_id
                    role['aws_iam_policies'] = []
                    role['user_ids'] = []
                    role['user_group_ids'] = []
                    role['account_ids'] = []
                    role['future_accounts'] = r['future_accounts']
                    role['long_term_access_keys'] = r['long_term_access_keys']
                    role['short_term_access_keys'] = r['short_term_access_keys']
                    role['web_access'] = r['web_access']

                    # get extra metadata that we need
                    url = "%s/v3/project-cloud-access-role/%s" % (BASE_URL, r_id)
                    proj_details = api_call(url)
                    if proj_details:

                      if proj_details['aws_iam_policies'] is not None:
                        for i in proj_details['aws_iam_policies']:
                            role['aws_iam_policies'].append(i['id'])

                      if proj_details['users'] is not None:
                        for u in proj_details['users']:
                            role['user_ids'].append(u['id'])

                      if proj_details['user_groups'] is not None:
                        for g in proj_details['user_groups']:
                            role['user_group_ids'].append(g['id'])

                      if proj_details['accounts'] is not None:
                        for a in proj_details['accounts']:
                            role['account_ids'].append(a['id'])

                      if 'aws_iam_permissions_boundary' in proj_details:
                        # sys.exit(json.dumps(proj_details))
                        if proj_details['aws_iam_permissions_boundary'] is not None:
                          role['aws_iam_permissions_boundary'] = proj_details['aws_iam_permissions_boundary']['id']
                        else:
                          role['aws_iam_permissions_boundary'] = 'null'
                    else:
                        print("\tDetails for Project role %s weren't found. Data will be incomplete. Skipping" % r['name'])
                        print("\tReceived data: %s" % proj_details)
                        incomplete_projs.append(r['name'])
                        continue

                    # check for iam path
                    if 'aws_iam_path' in r:
                      role['aws_iam_path'] = r['aws_iam_path']
                    else:
                      role['aws_iam_path'] = ''

                    template = textwrap.dedent('''\
                        resource "{resource_type}" "{resource_id}" {{
                            # id                          = {id}
                            name                        = "{resource_name}"
                            project_id                  = {project_id}
                            aws_iam_role_name           = "{aws_iam_role_name}"
                            aws_iam_path                = "{aws_iam_path}"
                            aws_permissions_boundary_id = {aws_perm_boundary}
                            short_term_access_keys      = {short_term_access_keys}
                            long_term_access_keys       = {long_term_access_keys}
                            web_access                  = {web_access}
                            future_accounts             = {future_accounts}
                            {aws_iam_policies}
                            {accounts}
                            {users}
                            {user_groups}
                        }}

                        output "{resource_id}" {{
                            value = {resource_type}.{resource_id}.id
                        }}''')

                    content = template.format(
                        resource_type="%s_project_cloud_access_role" % RESOURCE_PREFIX,
                        resource_id=normalize_string(role['name']),
                        resource_name=role['name'],
                        id=r_id,
                        project_id=proj_id,
                        aws_iam_role_name=role['aws_iam_role_name'],
                        aws_iam_path=role['aws_iam_path'],
                        aws_perm_boundary=role['aws_iam_permissions_boundary'],
                        short_term_access_keys=str(role['short_term_access_keys']).lower(),
                        long_term_access_keys=str(role['long_term_access_keys']).lower(),
                        web_access=str(role['web_access']).lower(),
                        future_accounts=str(role['future_accounts']).lower(),
                        aws_iam_policies=process_list(role['aws_iam_policies'], "aws_iam_policies"),
                        accounts=process_list(role['account_ids'], "accounts"),
                        users=process_list(role['user_ids'], "users"),
                        user_groups=process_list(role['user_group_ids'], "user_groups"),
                    )

                    # write the metadata file
                    if ARGS.prepend_id:
                        base_filename = normalize_string(role['name'], r_id)
                    else:
                        base_filename = normalize_string(role['name'])

                    filename = "%s/project-cloud-access-role/%s/%s.tf" % (ARGS.import_dir, proj_dir, base_filename)

                    write_file(filename, process_template(content))

                    # add to IMPORTED_RESOURCES
                    resource = "module.project-cloud-access-role.%s_project_cloud_access_role.%s %s" % (RESOURCE_PREFIX, normalize_string(role['name']), r_id)
                    IMPORTED_RESOURCES.append(resource)

            else:
                print("Found 0 roles on Project (ID: %s) %s" % (proj_id, proj['name']))

    if incomplete_projs != []:
        print("Project roles that failed to return full details:")
        for p in incomplete_projs:
            print(p)

    # now out of the loop, write the provider.tf file
    provider_filename = "%s/project-cloud-access-role/provider.tf" % ARGS.import_dir
    write_provider_file(provider_filename, PROVIDER_TEMPLATE)

    print("Done.")
    return True


def import_ou_roles():
    """
    Import OU Cloud Access Roles

    Handles full process to import OU Access Roles

    Returns:
        True
    """
    print("\nImporting OU Cloud Access Roles\n--------------------------")

    base_path = ARGS.import_dir + "/ou-cloud-access-role/"

    # first we need a list of all ous in cloudtamer
    all_ous = get_objects_or_ids('ous')

    if all_ous:
        IMPORTED_MODULES.append("ou-cloud-access-role")

        incomplete_ous = []

        for ou in all_ous:
            ou_id = ou['id']

            # get the normalized name for this OU
            ou_name = normalize_string(ou['name'])

            # create the directory name for this OU
            # it will be of the format {ID}-{normalized_name}
            # Ex: 13-Test_OU
            ou_dir = "%s-%s" % (str(ou_id), ou_name)

            # get the list of roles for this ou
            roles = get_ou_roles(ou_id)

            if roles:
                print("Found %s roles on OU (ID: %s) %s" % (len(roles), ou_id, ou['name']))

                # create a folder for this ou to keep all roles together
                if not os.path.isdir(base_path+ou_dir):
                    os.mkdir(base_path+ou_dir)

                for r in roles:
                    # pull out the id for this role
                    r_id = r['id']

                    # init new role object
                    role = {}
                    role['name'] = r['name']
                    role['aws_iam_role_name'] = r['aws_iam_role_name']
                    role['ou_id'] = ou_id
                    role['aws_iam_policies'] = []
                    role['user_ids'] = []
                    role['user_group_ids'] = []

                    # get extra metadata that we need
                    url = "%s/v3/ou-cloud-access-role/%s" % (BASE_URL, r_id)
                    ou_details = api_call(url)
                    if ou_details:
                        role['long_term_access_keys'] = ou_details['ou_cloud_access_role']['long_term_access_keys']
                        role['short_term_access_keys'] = ou_details['ou_cloud_access_role']['short_term_access_keys']
                        role['web_access'] = ou_details['ou_cloud_access_role']['web_access']

                        if ou_details['aws_iam_policies'] is not None:
                          for i in ou_details['aws_iam_policies']:
                              role['aws_iam_policies'].append(i['id'])

                        if ou_details['users'] is not None:
                          for u in ou_details['users']:
                              role['user_ids'].append(u['id'])

                        if ou_details['user_groups'] is not None:
                          for g in ou_details['user_groups']:
                              role['user_group_ids'].append(g['id'])

                        if 'aws_iam_permissions_boundary' in ou_details:
                          if ou_details['aws_iam_permissions_boundary'] is not None:
                            role['aws_iam_permissions_boundary'] = ou_details['aws_iam_permissions_boundary']['id']
                          else:
                            role['aws_iam_permissions_boundary'] = 'null'
                    else:
                        print("\tDetails for OU role %s weren't found. Data will be incomplete. Skipping" % r['name'])
                        print("\tReceived data: %s" % ou_details)
                        incomplete_ous.append(r['name'])
                        continue

                    # check for iam path
                    if 'aws_iam_path' in r:
                      role['aws_iam_path'] = r['aws_iam_path']
                    else:
                      role['aws_iam_path'] = ''

                    template = textwrap.dedent('''\
                        resource "{resource_type}" "{resource_id}" {{
                            # id                          = {id}
                            name                        = "{resource_name}"
                            ou_id                       = {ou_id}
                            aws_iam_role_name           = "{aws_iam_role_name}"
                            aws_iam_path                = "{aws_iam_path}"
                            aws_permissions_boundary_id = {aws_perm_boundary}
                            short_term_access_keys      = {short_term_access_keys}
                            long_term_access_keys       = {long_term_access_keys}
                            web_access                  = {web_access}
                            {aws_iam_policies}
                            {users}
                            {user_groups}
                        }}

                        output "{resource_id}" {{
                            value = {resource_type}.{resource_id}.id
                        }}''')

                    content = template.format(
                        resource_type="%s_ou_cloud_access_role" % RESOURCE_PREFIX,
                        resource_id=normalize_string(role['name']),
                        resource_name=role['name'],
                        id=r_id,
                        ou_id=ou_id,
                        aws_iam_role_name=role['aws_iam_role_name'],
                        aws_iam_path=role['aws_iam_path'],
                        aws_perm_boundary=role['aws_iam_permissions_boundary'],
                        short_term_access_keys=str(role['short_term_access_keys']).lower(),
                        long_term_access_keys=str(role['long_term_access_keys']).lower(),
                        web_access=str(role['web_access']).lower(),
                        aws_iam_policies=process_list(role['aws_iam_policies'], "aws_iam_policies"),
                        users=process_list(role['user_ids'], "users"),
                        user_groups=process_list(role['user_group_ids'], "user_groups"),
                    )

                    # write the metadata file
                    if ARGS.prepend_id:
                        base_filename = normalize_string(role['name'], r_id)
                    else:
                        base_filename = normalize_string(role['name'])

                    filename = "%s/ou-cloud-access-role/%s/%s.tf" % (ARGS.import_dir, ou_dir, base_filename)

                    write_file(filename, process_template(content))

                    # add to IMPORTED_RESOURCES
                    resource = "module.ou-cloud-access-role.%s.%s_ou_cloud_access_role.%s %s" % (RESOURCE_PREFIX, ou_dir, normalize_string(role['name']), r_id)
                    IMPORTED_RESOURCES.append(resource)

            else:
                print("Found 0 roles on OU (ID: %s) %s" % (ou_id, ou['name']))

    if incomplete_ous != []:
        print("OU roles that failed to return full details:")
        for p in incomplete_ous:
            print(p)

    # now out of the loop, write the provider.tf file
    provider_filename = "%s/ou-cloud-access-role/provider.tf" % ARGS.import_dir
    write_provider_file(provider_filename, PROVIDER_TEMPLATE)

    print("Done.")
    return True


def import_cloud_rules():
    """
    Import Cloud Rules

    Handles full process to import Cloud Rules

    Returns:
        True
    """
    print("\nImporting Cloud Rules\n--------------------------")
    url = '%s/v3/cloud-rule' % BASE_URL
    cloud_rules = api_call(url)

    if cloud_rules:
        print("Found %s Cloud Rules" % len(cloud_rules))
        IMPORTED_MODULES.append("cloud-rule")

        # now loop over them and get the CFT and IAM policy associations
        for c in cloud_rules:

            # skip the built_in rules
            if c['built_in']:
                print("Skipping built-in Cloud Rule: %s" % c['name'])
                continue

            print("Importing Cloud Rule - %s" % c['name'])

            cloud_rule = get_cloud_rule(c['id'])

            if cloud_rule:
                c['arm_templates']              = get_objects_or_ids('azure_arm_template_definitions', cloud_rule)
                c['azure_policy_definitions']   = get_objects_or_ids('azure_policy_definitions', cloud_rule)
                c['azure_role_definitions']     = get_objects_or_ids('azure_role_definitions', cloud_rule)
                c['cfts']                       = get_objects_or_ids('aws_cloudformation_templates', cloud_rule)
                c['compliance_standard_ids']    = get_objects_or_ids('compliance_standards', cloud_rule)
                c['iam_policy_ids']             = get_objects_or_ids('aws_iam_policies', cloud_rule)
                c['internal_ami_ids']           = get_objects_or_ids('internal_aws_amis', cloud_rule)
                c['ou_ids']                     = get_objects_or_ids('ous', cloud_rule)
                c['portfolio_ids']              = get_objects_or_ids('internal_aws_service_catalog_portfolios', cloud_rule)
                c['project_ids']                = get_projects(cloud_rule)
                c['scp_ids']                    = get_objects_or_ids('service_control_policies', cloud_rule)
            else:
                print("Failed getting Cloud Rule details.")

            # get owner user and group IDs formatted into required format
            owner_users     = process_owners(cloud_rule['owner_users'], 'owner_users')
            owner_groups    = process_owners(cloud_rule['owner_user_groups'], 'owner_user_groups')

            for i in ["pre_webhook_id", "post_webhook_id"]:
                if c[i] is None:
                    c[i] = 'null'

            template = textwrap.dedent('''\
                resource "{resource_type}" "{resource_id}" {{
                    # id                                      = {id}
                    name                                    = "{resource_name}"
                    description                             = "{description}"
                    pre_webhook_id                          = {pre_webhook_id}
                    post_webhook_id                         = {post_webhook_id}
                    {aws_iam_policies}
                    {cfts}
                    {azure_arm_template_definitions}
                    {azure_policy_definitions}
                    {azure_role_definitions}
                    {compliance_standards}
                    {amis}
                    {portfolios}
                    {scps}
                    {ous}
                    {projects}
                    {owner_users}
                    {owner_groups}
                }}

                output "{resource_id}" {{
                    value = {resource_type}.{resource_id}.id
                }}''')

            content = template.format(
                resource_type="%s_cloud_rule" % RESOURCE_PREFIX,
                resource_id=normalize_string(c['name']),
                resource_name=c['name'],
                id=c['id'],
                description=c['description'],
                pre_webhook_id=c['pre_webhook_id'],
                post_webhook_id=c['post_webhook_id'],
                aws_iam_policies=process_list(c['iam_policy_ids'], "aws_iam_policies"),
                cfts=process_list(c['cfts'], "aws_cloudformation_templates"),
                azure_arm_template_definitions=process_list(c['arm_templates'], "azure_arm_template_definitions"),
                azure_policy_definitions=process_list(c['azure_policy_definitions'], "azure_policy_definitions"),
                azure_role_definitions=process_list(c['azure_role_definitions'], "azure_role_definitions"),
                compliance_standards=process_list(c['compliance_standard_ids'], "compliance_standards"),
                amis=process_list(c['internal_ami_ids'], "internal_aws_amis"),
                portfolios=process_list(c['portfolio_ids'], "internal_aws_service_catalog_portfolios"),
                scps=process_list(c['scp_ids'], "service_control_policies"),
                ous=process_list(c['ou_ids'], "ous"),
                projects=process_list(c['project_ids'], "projects"),
                owner_users='\n    '.join(owner_users),
                owner_groups='\n    '.join(owner_groups),
            )

            # construct the metadata file name
            if ARGS.prepend_id:
                base_filename = normalize_string(c['name'], c['id'])
            else:
                base_filename = normalize_string(c['name'])

            filename = "%s/cloud-rule/%s.tf" % (ARGS.import_dir, base_filename)

            write_file(filename, process_template(content))

            # add to IMPORTED_RESOURCES
            resource = "module.cloud-rule.%s_cloud_rule.%s %s" % (RESOURCE_PREFIX, normalize_string(c['name']), c['id'])
            IMPORTED_RESOURCES.append(resource)

        # now out of the loop, write the provider.tf file
        provider_filename = "%s/cloud-rule/provider.tf" % ARGS.import_dir
        write_provider_file(provider_filename, PROVIDER_TEMPLATE)

        print("Done.")
        return True
    else:
        print("Error while importing Cloud Rules.")
        return False


def import_compliance_checks():
    """
    Import Compliance Checks

    Handles full process to import compliance checks

    Returns:
        success - True
        failure - False
    """
    CHECKS = get_comp_checks()

    if CHECKS:
        print("\nImporting Compliance Checks\n--------------------------")
        print("Found %s Compliance Checks" % len(CHECKS))
        IMPORTED_MODULES.append("compliance-check")

        for c in CHECKS:
            # skip cloudtamer managed checks
            if c['ct_managed']:
                print("Skipping built-in Compliance Check - %s" % c['name'])
                continue

            print("Importing Compliance Check - %s" % c['name'])

            # init new check object
            check = {}
            check['name']                       = process_string(c['name'])
            check['description']                = process_string(c['description'])
            check['regions']                    = c['regions']
            check['azure_policy_id']            = c['azure_policy_id']
            check['cloud_provider_id']          = c['cloud_provider_id']
            check['compliance_check_type_id']   = c['compliance_check_type_id']
            check['severity_type_id']           = c['severity_type_id']
            check['frequency_minutes']          = c['frequency_minutes']
            check['frequency_type_id']          = c['frequency_type_id']
            check['is_all_regions']             = c['is_all_regions']
            check['is_auto_archived']           = c['is_auto_archived']
            check['body']                       = c['body'].rstrip()
            check['owner_user_ids']             = []
            check['owner_user_group_ids']       = []


            # we need to make an additional call to get owner users and groups
            url = "%s/v3/compliance/check/%s" % (BASE_URL, c['id'])
            details = api_call(url)

            # get owner user and group IDs formatted into required format
            if details:
                owner_users     = process_owners(details['owner_users'], 'owner_users')
                owner_groups    = process_owners(details['owner_user_groups'], 'owner_user_groups')
            else:
                print("Failed to get details for check %s" % check['name'])
                print(json.dumps(details))

            # properly format regions based on contents
            if check['regions'][0] == '':
                check['regions'] = []
            else:
                check['regions'] = json.dumps(check['regions'])

            # calculate minutes based on frequency type
            if check['frequency_type_id'] == int(3):
                check['frequency_minutes'] = check['frequency_minutes'] // 60   # hourly, divide minutes by 60
            elif check['frequency_type_id'] == int(4):
                check['frequency_minutes'] = check['frequency_minutes'] // 1440 # daily, divide minutes by 1440

            # double all single dollar signs to be valid for TF format
            # check['body'] = re.sub(r'\${1}\{', r'$${', check['body'])

            # build template based on cloud provider
            # AWS = 1
            # Azure = 2
            # GCP = 3
            if check['cloud_provider_id'] == 1:
                template = textwrap.dedent('''\
                    resource "{resource_type}" "{resource_id}" {{
                        # id                          = {id}
                        name                        = "{resource_name}"
                        description                 = "{description}"
                        created_by_user_id          = {created_by_user_id}
                        regions                     = {regions}
                        cloud_provider_id           = {cloud_provider_id} # 1 = AWS, 2 = Azure, 3 = GCP
                        compliance_check_type_id    = {compliance_check_type_id} # 1 = external, 2 = c7n, 3 = azure, 4 = tenable
                        severity_type_id            = {severity_type_id} # 5 = critical, 4 = high, 3 = medium, 2 = low, 1 = info
                        frequency_minutes           = {frequency_min}
                        frequency_type_id           = {frequency_type_id} # 2 = minutes, 3 = hours, 4 = days
                        is_all_regions              = {is_all_regions}
                        is_auto_archived            = {is_auto_archived}
                        {owner_users}
                        {owner_groups}

                        body = <<-EOT
                    {body}
                    EOT
                    }}

                    output "{resource_id}" {{
                        value = {resource_type}.{resource_id}.id
                    }}''')

                content = template.format(
                    resource_type="%s_compliance_check" % RESOURCE_PREFIX,
                    resource_id=normalize_string(check['name']),
                    resource_name=check['name'],
                    id=c['id'],
                    description=check['description'],
                    created_by_user_id=c['created_by_user_id'],
                    regions=check['regions'],
                    cloud_provider_id=check['cloud_provider_id'],
                    compliance_check_type_id=check['compliance_check_type_id'],
                    severity_type_id=check['severity_type_id'],
                    frequency_min=check['frequency_minutes'],
                    frequency_type_id=check['frequency_type_id'],
                    is_all_regions=str(check['is_all_regions']).lower(),
                    is_auto_archived=str(check['is_auto_archived']).lower(),
                    owner_users='\n    '.join(owner_users),
                    owner_groups='\n    '.join(owner_groups),
                    body=check['body']
                )
            elif check['cloud_provider_id'] == 2:
                if check['compliance_check_type_id'] == 1:
                    template = textwrap.dedent('''\
                        resource "{resource_type}" "{resource_id}" {{
                            # id                          = {id}
                            name                        = "{resource_name}"
                            description                 = "{description}"
                            created_by_user_id          = {created_by_user_id}
                            regions                     = {regions}
                            cloud_provider_id           = {cloud_provider_id} # 1 = AWS, 2 = Azure, 3 = GCP
                            compliance_check_type_id    = {compliance_check_type_id} # 1 = external, 2 = c7n, 3 = azure, 4 = tenable
                            severity_type_id            = {severity_type_id} # 5 = critical, 4 = high, 3 = medium, 2 = low, 1 = info
                            frequency_minutes           = {frequency_min}
                            frequency_type_id           = {frequency_type_id} # 2 = minutes, 3 = hours, 4 = days
                            is_all_regions              = {is_all_regions}
                            is_auto_archived            = {is_auto_archived}
                            {owner_users}
                            {owner_groups}
                        }}

                        output "{resource_id}" {{
                            value = {resource_type}.{resource_id}.id
                        }}''')

                    content = template.format(
                        resource_type="%s_compliance_check" % RESOURCE_PREFIX,
                        resource_id=normalize_string(check['name']),
                        resource_name=check['name'],
                        id=c['id'],
                        description=check['description'],
                        created_by_user_id=c['created_by_user_id'],
                        regions=check['regions'],
                        cloud_provider_id=check['cloud_provider_id'],
                        compliance_check_type_id=check['compliance_check_type_id'],
                        severity_type_id=check['severity_type_id'],
                        frequency_min=check['frequency_minutes'],
                        frequency_type_id=check['frequency_type_id'],
                        is_all_regions=str(check['is_all_regions']).lower(),
                        is_auto_archived=str(check['is_auto_archived']).lower(),
                        owner_users='\n    '.join(owner_users),
                        owner_groups='\n    '.join(owner_groups)
                    )
                elif check['compliance_check_type_id'] == 2:
                    template = textwrap.dedent('''\
                        resource "{resource_type}" "{resource_id}" {{
                            # id                          = {id}
                            name                        = "{resource_name}"
                            description                 = "{description}"
                            created_by_user_id          = {created_by_user_id}
                            regions                     = {regions}
                            cloud_provider_id           = {cloud_provider_id} # 1 = AWS, 2 = Azure, 3 = GCP
                            compliance_check_type_id    = {compliance_check_type_id} # 1 = external, 2 = c7n, 3 = azure, 4 = tenable
                            severity_type_id            = {severity_type_id} # 5 = critical, 4 = high, 3 = medium, 2 = low, 1 = info
                            frequency_minutes           = {frequency_min}
                            frequency_type_id           = {frequency_type_id} # 2 = minutes, 3 = hours, 4 = days
                            is_all_regions              = {is_all_regions}
                            is_auto_archived            = {is_auto_archived}
                            {owner_users}
                            {owner_groups}

                            body = <<-EOT
                        {body}
                        EOT
                        }}

                        output "{resource_id}" {{
                            value = {resource_type}.{resource_id}.id
                        }}''')

                    content = template.format(
                        resource_type="%s_compliance_check" % RESOURCE_PREFIX,
                        resource_id=normalize_string(check['name']),
                        resource_name=check['name'],
                        id=c['id'],
                        description=check['description'],
                        created_by_user_id=c['created_by_user_id'],
                        regions=check['regions'],
                        cloud_provider_id=check['cloud_provider_id'],
                        compliance_check_type_id=check['compliance_check_type_id'],
                        severity_type_id=check['severity_type_id'],
                        frequency_min=check['frequency_minutes'],
                        frequency_type_id=check['frequency_type_id'],
                        is_all_regions=str(check['is_all_regions']).lower(),
                        is_auto_archived=str(check['is_auto_archived']).lower(),
                        owner_users='\n    '.join(owner_users),
                        owner_groups='\n    '.join(owner_groups),
                        body=check['body']
                    )
                elif check['compliance_check_type_id'] == 3:
                    template = textwrap.dedent('''\
                        resource "{resource_type}" "{resource_id}" {{
                            # id                          = {id}
                            name                        = "{resource_name}"
                            description                 = "{description}"
                            created_by_user_id          = {created_by_user_id}
                            regions                     = {regions}
                            azure_policy_id             = {azure_policy_id}
                            cloud_provider_id           = {cloud_provider_id} # 1 = AWS, 2 = Azure, 3 = GCP
                            compliance_check_type_id    = {compliance_check_type_id} # 1 = external, 2 = c7n, 3 = azure, 4 = tenable
                            severity_type_id            = {severity_type_id} # 5 = critical, 4 = high, 3 = medium, 2 = low, 1 = info
                            frequency_minutes           = {frequency_min}
                            frequency_type_id           = {frequency_type_id} # 2 = minutes, 3 = hours, 4 = days
                            is_all_regions              = {is_all_regions}
                            is_auto_archived            = {is_auto_archived}
                            {owner_users}
                            {owner_groups}
                        }}

                        output "{resource_id}" {{
                            value = {resource_type}.{resource_id}.id
                        }}''')

                    content = template.format(
                        resource_type="%s_compliance_check" % RESOURCE_PREFIX,
                        resource_id=normalize_string(check['name']),
                        resource_name=check['name'],
                        id=c['id'],
                        description=check['description'],
                        created_by_user_id=c['created_by_user_id'],
                        regions=check['regions'],
                        azure_policy_id=check['azure_policy_id'],
                        cloud_provider_id=check['cloud_provider_id'],
                        compliance_check_type_id=check['compliance_check_type_id'],
                        severity_type_id=check['severity_type_id'],
                        frequency_min=check['frequency_minutes'],
                        frequency_type_id=check['frequency_type_id'],
                        is_all_regions=str(check['is_all_regions']).lower(),
                        is_auto_archived=str(check['is_auto_archived']).lower(),
                        owner_users='\n    '.join(owner_users),
                        owner_groups='\n    '.join(owner_groups)
                    )
                else:
                    print("Unhandled compliance_check_type_id: %s" % check['compliance_check_type_id'])
            elif check['cloud_provider_id'] == 3:
                template = textwrap.dedent('''\
                    resource "{resource_type}" "{resource_id}" {{
                        # id                          = {id}
                        name                        = "{resource_name}"
                        description                 = "{description}"
                        created_by_user_id          = {created_by_user_id}
                        regions                     = {regions}
                        cloud_provider_id           = {cloud_provider_id} # 1 = AWS, 2 = Azure, 3 = GCP
                        compliance_check_type_id    = {compliance_check_type_id} # 1 = external, 2 = c7n, 3 = azure, 4 = tenable
                        severity_type_id            = {severity_type_id} # 5 = critical, 4 = high, 3 = medium, 2 = low, 1 = info
                        frequency_minutes           = {frequency_min}
                        frequency_type_id           = {frequency_type_id} # 2 = minutes, 3 = hours, 4 = days
                        is_all_regions              = {is_all_regions}
                        is_auto_archived            = {is_auto_archived}
                        {owner_users}
                        {owner_groups}

                        body = <<-EOT
                    {body}
                    EOT
                    }}

                    output "{resource_id}" {{
                        value = {resource_type}.{resource_id}.id
                    }}''')

                content = template.format(
                    resource_type="%s_compliance_check" % RESOURCE_PREFIX,
                    resource_id=normalize_string(check['name']),
                    resource_name=check['name'],
                    id=c['id'],
                    description=check['description'],
                    created_by_user_id=c['created_by_user_id'],
                    regions=check['regions'], ensure_ascii=True,
                    cloud_provider_id=check['cloud_provider_id'],
                    compliance_check_type_id=check['compliance_check_type_id'],
                    severity_type_id=check['severity_type_id'],
                    frequency_min=check['frequency_minutes'],
                    frequency_type_id=check['frequency_type_id'],
                    is_all_regions=str(check['is_all_regions']).lower(),
                    is_auto_archived=str(check['is_auto_archived']).lower(),
                    owner_users='\n    '.join(owner_users),
                    owner_groups='\n    '.join(owner_groups),
                    body=check['body']
                )
            else:
                print("Skipping. Unhandled cloud_provider_id found: %s" % check['cloud_provider_id'])
                continue

            # for external and tenable checks, remove the empty body block
            if check['compliance_check_type_id'] == 1 or check['compliance_check_type_id'] == 4:
                content = re.sub(r'\s*body = <<-EOT\n\nEOT', '', content, re.MULTILINE)

            # build the file names
            if ARGS.prepend_id:
                base_filename = normalize_string(check['name'], c['id'])
            else:
                base_filename = normalize_string(check['name'])

            filename = "%s/compliance-check/%s.tf" % (ARGS.import_dir, base_filename)

            write_file(filename, process_template(content))

            # add to IMPORTED_RESOURCES
            resource = "module.compliance-check.%s_compliance_check.%s %s" % (RESOURCE_PREFIX, normalize_string(check['name']), c['id'])
            IMPORTED_RESOURCES.append(resource)

        # now out of the loop, write the provider.tf file
        provider_filename = "%s/compliance-check/provider.tf" % ARGS.import_dir
        write_provider_file(provider_filename, PROVIDER_TEMPLATE)

        print("Done.")
        return True
    else:
        print("Error while importing Compliance Checks.")
        return False


def import_compliance_standards():
    """
    Import Compliance Standards

    Handles full process to import compliance standards

    Returns:
        success - True
        failure - False
    """
    STANDARDS = get_objects_or_ids('compliance_standards')

    if STANDARDS:
        print("\nImporting Compliance Standards\n--------------------------")
        print("Found %s Compliance Standards" % len(STANDARDS))
        IMPORTED_MODULES.append("compliance-standard")

        for s in STANDARDS:

            # skip cloudtamer managed checks
            if s['ct_managed']:
                print("Skipping built-in Compliance Standard - %s" % s['name'])
                continue

            print("Importing Compliance Standard - %s" % s['name'])

            # init new object
            standard = {}
            standard['name'] = process_string(s['name'])
            standard['checks'] = []
            standard['owner_user_ids'] = []
            standard['owner_user_group_ids'] = []
            standard['description'] = ''
            standard['created_by_user_id'] = ''

            # we need to make an additional call to get attached checks, owner users and groups
            url = "%s/v3/compliance/standard/%s" % (BASE_URL, s['id'])
            details = api_call(url)
            if details:
                if 'description' in details['compliance_standard']:
                    standard['description'] = details['compliance_standard']['description']
                if 'created_by_user_id' in details['compliance_standard']:
                    standard['created_by_user_id'] = details['compliance_standard']['created_by_user_id']
                for c in details['compliance_checks']:
                    standard['checks'].append(c['id'])

            # get owner user and group IDs formatted into required format
            owner_users     = process_owners(details['owner_users'], 'owner_users')
            owner_groups    = process_owners(details['owner_user_groups'], 'owner_user_groups')

            # format the list of compliance check IDs into a multiline string
            # that prints nicely in the template
            # checks = ''
            # for check in standard['checks']:
            #     if check != standard['checks'][-1]:
            #         checks += "\n        %s," % check
            #     else:
            #         checks += "\n        %s" % check

            # checks    = []
            # for i in standard['checks']:
            #     line = "compliance_checks { id = %s }" % i
            #     checks.append(line)

            template = textwrap.dedent('''\
                resource "{resource_type}" "{resource_id}" {{
                    # id                          = {id}
                    name                        = "{resource_name}"
                    description                 = "{description}"
                    created_by_user_id          = {created_by_user_id}
                    {owner_users}
                    {owner_groups}
                    {compliance_checks}
                }}

                output "{resource_id}" {{
                    value = {resource_type}.{resource_id}.id
                }}''')

            content = template.format(
                resource_type="%s_compliance_standard" % RESOURCE_PREFIX,
                resource_id=normalize_string(standard['name']),
                id=s['id'],
                resource_name=standard['name'],
                description=standard['description'],
                created_by_user_id=standard['created_by_user_id'],
                owner_users='\n    '.join(owner_users),
                owner_groups='\n    '.join(owner_groups),
                compliance_checks=process_list(standard['checks'], "compliance_checks")
            )

            # build the file names
            if ARGS.prepend_id:
                base_filename = normalize_string(standard['name'], s['id'])
            else:
                base_filename = normalize_string(standard['name'])

            filename = "%s/compliance-standard/%s.tf" % (ARGS.import_dir, base_filename)

            write_file(filename, process_template(content))

            # add to IMPORTED_RESOURCES
            resource = "module.compliance-standard.%s_compliance_standard.%s %s" % (RESOURCE_PREFIX, normalize_string(standard['name']), s['id'])
            IMPORTED_RESOURCES.append(resource)

        # now out of the loop, write the provider.tf file
        provider_filename = "%s/compliance-standard/provider.tf" % ARGS.import_dir
        write_provider_file(provider_filename, PROVIDER_TEMPLATE)

        print("Done.")
        return True
    else:
        print("Error while importing Compliance Standards.")
        return False


def get_cloud_rule(c_id):
    """
    Get Cloud Rule

    Receives a cloud rule ID and returns the full object
    that contains all associated resources

    Params:
        c_id (int) - ID of the Cloud Rule to return

    Return:
        success - cloud_rule (dict)
        failure - False
    """
    url = '%s/v3/cloud-rule/%s' % (BASE_URL, c_id)
    cloud_rule = api_call(url)
    if cloud_rule:
        return cloud_rule
    else:
        return False


def get_projects(cloud_rule=False):
    """
    Get Projects

    Params:
        cloud_rule (dict) - cloud rule object for which to return project IDs where the cloud rule is applied locally
                            if not set, it will return a list of all projects from cloudtamer
    Return:
        success - list of project IDs or project objects (based on cloud_rule param)
        failure - False
    """
    if cloud_rule:
        ids = []

        # pull out the ID of the provided cloud rule
        c_id = cloud_rule['cloud_rule']['id']

        # for each project, call the v3/project/{id}/cloud-rule endpoint
        # to get it's locally applied cloud rules. Then check if
        # c_id is in that list of cloud rules
        for p in cloud_rule['projects']:
            p_id = p['id']
            url = "%s/v3/project/%s/cloud-rule" % (BASE_URL, p_id)
            project_rules = api_call(url)
            if project_rules:
                for rule in project_rules:
                    if rule['id'] == c_id:
                        if p_id not in ids:
                            ids.append(p_id)
        return ids
    else:
        url = '%s/v3/project' % BASE_URL
        projects = api_call(url)
        if projects:
            return projects
        else:
            print("Could not get projects from cloudtamer.")
            return False


def get_ou_roles(ou_id):
    """
    Get OU Roles

    Returns a list of role objects that are assigned locally at OU with the given ID.

    This function is needed because the endpoint "v3/ou/{id}/ou-cloud-access-role"
    returns inherited roles too, which we don't want, so we have to do some extra work
    to only get the local roles.

    Params:
        ou_id (int) - ID of the OU for which to return locally applied roles

    Return:
        success - a list of role objects
        failure - False
    """
    url = "%s/v3/ou/%s/ou-cloud-access-role" % (BASE_URL, ou_id)
    roles = api_call(url)
    ROLES = []
    if roles:
        for role in roles:
            if role['ou_id'] == ou_id:
                ROLES.append(role)
        return ROLES
    else:
        return False


def get_comp_checks(comp_standard=False):
    """
    Get Compliance Checks

    Params:
        comp_standard (dict) -  compliance_standard object for which to return
                                associated compliance standard IDs
                                if not set, it will return a list of all compliance check
                                objects from cloudtamer
    Return:
        ids (list) - list of compliance standard IDs
    """
    if comp_standard:
        ids = []
        for i in comp_standard['compliance_checks']:
            ids.append(i['id'])
        return ids
    else:
        url = "%s/v3/compliance/check" % BASE_URL
        checks = api_call(url)
        if checks:
            return checks
        else:
            print("Could not get Compliance Checks from cloudtamer.")
            return False


def get_objects_or_ids(object_type, cloud_rule=False):
    """
    Generic helper function to either return all objects of object_type from cloudtamer
    or if cloud_rule is set, return IDs of the associated object_type in cloud_rule

    Params:
        object_type     (str)   -   the type of object to get from the cloud rule, or out of cloudtamer
                                    must be one of the keys of object_type_to_api_map
        cloud_rule      (dict)  -   the cloud_rule object to return IDs of object_type. If not set, this
                                    function will return all objects of object_type

    Return:
        Success:
            if cloud_rule:  ids     (list)  - list of IDs of object_type found in cloud_rule
            else:           objects (list)  - list of objects of object_type
        Failure:
            False   (bool)
    """

    # this maps the various object types that can be attached to cloud rules
    # to the GET endpoint that returns all of those objects out of cloudtamer
    object_type_to_api_map = {
        'aws_cloudformation_templates': 'v3/cft',
        'aws_iam_policies': 'v3/iam-policy',
        'azure_arm_template_definitions': 'v3/azure-arm-template',
        'azure_policy_definitions': 'v3/azure-policy',
        'azure_role_definitions': 'v3/azure-role',
        'compliance_standards': 'v3/compliance/standard',
        'internal_aws_amis': 'v3/ami',
        'internal_aws_service_catalog_portfolios': 'v3/service-catalog',
        'ous': 'v3/ou',
        'owner_user_groups': 'v3/user-group',
        'owner_users': 'v3/user',
        'service_control_policies': 'v3/service-control-policy'
    }

    if cloud_rule:
        ids = []
        for i in cloud_rule[object_type]:
            ids.append(i['id'])
        return ids
    else:
        api_endpoint = object_type_to_api_map[object_type]
        url = "%s/%s" % (BASE_URL, api_endpoint)
        objects = api_call(url)
        if objects:
            return objects
        else:
            print("Could not get return from %s endpoint from cloudtamer." % url)
            return False


def normalize_string(string, id_ = False):
    """
    Normalize String

    Receives a string and normalizes it for proper source control handling

    Params:
        name (str)  - original string
        id_ (int)   - id of the resource. If set, it will be prepended to filename

    Return:
        string (str) - normalized string
    """
    # replace spaces with underscores
    string = re.sub(r'\s', '_', string)
    # remove all non alphanumeric characters
    string = re.sub(r'[^A-Za-z0-9_-]', '', string)

    # prepend {ID} if id_ is set
    if id_:
        string = "%s-%s" % (id_, string)

    return string


def write_file(file_name, content):
    """
    Write File

    Writes the given file_name with given content.
    Based on file_type, it will determine how to write the file,
    either as-is or using json.dump.

    Params:
        file_name   (str)           - name of the file to write. Expecting absolute path.
        content     (str)           - content to write to file_name

    Return:
        success - True
    """

    # only proceed if filename doesn't exist yet or the overwrite flag was set
    if not os.path.exists(file_name) or ARGS.overwrite:
        with open(file_name, 'w', encoding='utf8') as outfile:
            outfile.write(content)
    #else:
        #print("Found %s already. Will not overwrite." % file_name)

    return True


def read_file(file, content_type):
    """
    Read File

    Reads in the provided file and returns the content

    Params:
        file (str)          - name of the file to write. Expecting full path.
        content_type (str)  - type of file content (json, yaml, yml)

    Return:
        success - content of file
        failure - False
      """
    with open(file, "r", encoding='utf8') as f:
        if content_type == "json":
            # validate that the file contains json
            try:
                data = json.load(f)
            except:
                print("Failed to load json file %s." % file)
                return False
            else:
                return data


def write_provider_file(file_name, content):
    """
    Write Provider File

    Writes the provider.tf file with provided content

    If the file already exists, it will instead print out a
    provider.tf.example file with the text needed by the
    cloudtamer.io TF provider

    Params:
        file_name   (str)   - full file name including path to write
        content     (str)   - content to write into the file
    """

    if os.path.exists(file_name):
        file_name = "%s.example" % file_name

    with open(file_name, 'w', encoding='utf8') as outfile:
        outfile.write(content)

    return True

def write_resource_import_script(args, imported_resources):
    """
    Write Resource Import Script

    Writes a bash script to automate imported the current state of
    all resources that were just imported by the script

    Params:
        args                (dict)      - CLI ARGS
        imported_resources  (list)      - the IMPORTED_RESOURCES list
    """

    file_name = "%s/import_resource_state.sh" % args.import_dir
    with open(file_name, 'w', encoding='utf8') as outfile:
        outfile.write("#!/bin/bash\n")
        for line in IMPORTED_RESOURCES:
            outfile.write("terraform import %s\n" % line)

    return True


def api_call(url, timeout=30, test=False):
    """
    API Call

    Common helper function for making the API calls needed for this script.
    They are all GET requests.

    Params:
        url         (str)   - full URL to call
        timeout     (int)   - timeout for the call, defaults to 10
        test        (bool)  - if true, just test success of response and return
                              True / False accordingly, rather than returning the response data

    Return:
        success - response['data']
        failure - False
    """
    # check for the skip_ssl_verify flag
    if ARGS.skip_ssl_verify:
        verify = False
    else:
        verify = True

    try:
        response = requests.get(url=url, headers=HEADERS, timeout=timeout, verify=verify)
    except requests.exceptions.Timeout:
        print("Connection to %s timed out. Timeout set to: %s" % (url, timeout))
        return False
    except requests.exceptions.TooManyRedirects as e:
        print("Connection to %s returned Too Many Redirects error: %s" % (url, e))
        return False
    except requests.exceptions.RequestException as e:
        print("Connection to %s resulted in error: %s" % (url, e))
        return False
    except Exception as e:
        print("Exception occurred during connection to %s: %s" % (url, e))
        return False
    else:

        # at this point, no exceptions were thrown so the
        # the request succeeded

        # check if test is True, if so return True
        if test:
            return True

        # test for valid json response
        try:
            response.json()
        except JSONDecodeError as e:
            print("JSON decode error on response: %s, %s" % (response, e))
            return False
        else:
            response = response.json()

        if response['status'] == 200:
            # reset the unauth retry counter
            global UNAUTH_RETRY_COUNTER
            UNAUTH_RETRY_COUNTER = 0
            return response['data']
        elif response['status'] == 401:
            # retry up to MAX_UNAUTH_RETRIES
            if UNAUTH_RETRY_COUNTER < MAX_UNAUTH_RETRIES:
                retries = MAX_UNAUTH_RETRIES - UNAUTH_RETRY_COUNTER
                print("Received unauthorized response. Will retry %s more times." % retries)
                UNAUTH_RETRY_COUNTER += 1
                api_call(url)
            else:
                print("Hit max unauth retries.")
                return False
        else:
            print(response['status'])
            print("Error calling API: %s\n%s" % (url, response))
        return False


def validate_connection(url):
    """
    Validate Connection

    Make sure that the supplied CT URL can be reached

    Params:
        url (str) - the provided ct_url argument

    Returns:
        success - True
        failure - sys.exit
    """

    if api_call(url, 30, True):
        return True
    else:
        sys.exit("Unable to connect to %s" % url)


def validate_import_dir(path):
    """
    Validate Import Directory

    Make sure the import directory entered has the proper sub-directories
    for the resources being imported.

    Params:
        path (str) - value of ARGS.import_dir

    Returns:
        success - True
        failure - sys.exit with message
    """
    missing_dirs = []
    dir_map = {
        'aws-cloudformation-template': ARGS.skip_cfts,
        'aws-iam-policy': ARGS.skip_iams,
        'cloud-rule': ARGS.skip_cloud_rules,
        'ou-cloud-access-role': ARGS.skip_ou_roles,
        'project-cloud-access-role': ARGS.skip_project_roles,
        'compliance-check': ARGS.skip_checks,
        'compliance-standard': ARGS.skip_standards,
    }

    if os.path.isdir(path):
        for folder, flag in dir_map.items():
            if not flag:
                if not os.path.isdir("%s/%s" % (path, folder)):
                    missing_dirs.append(folder)

        if missing_dirs != []:
            print("%s is missing the following sub-directories:" % path)
            for d in missing_dirs:
                print("- %s" % d)

            create = input("Create them? (y/N) ")
            if create == "y":
                for d in missing_dirs:
                    dir = "%s/%s" % (path,d)
                    os.mkdir(dir)
                print("Done. You can now re-run the previous command.")
                sys.exit()
            else:
                sys.exit()
    else:
        sys.exit("Did not find import directory: %s" % path)

    return True


def process_owners(input, text):
    """
    Process the passed list of owner_users or owner_user_groups into the format
    required for the TF config files

    Param:
        input   (list)  - list of owner user objects returned from cloudtamer
        text    (str)   - text to prepend to each line in output
                            ('owner_users' or 'owner_user_groups')

    Return:
        output (list)       - processed list of owner user IDs
    """
    ids = []
    output = []

    # get all of the user IDs, store in ids
    for i in input:
        if 'id' in i:
            ids.append(i['id'])

    if len(ids):
        for i in ids:
            line = "%s { id = %s }" % (text, i)
            output.append(line)
    else:
        output.append("%s { }" % text)
    return output


def process_list(input, text):
    """
    Process a list of IDs into a multi-line list of
    objects as required by TF

    Param:
        input   (list)      - list of IDs to process
        text    (str)       - text to prepend to each line

    Return:
        output  (str)      - multi-line string list of objects
    """

    output = []

    if len(input):
        for i in input:
            line = "%s { id = %s }" % (text, i)
            output.append(line)
    else:
        line = "%s { }" % text
        output.append(line)

    return '\n    '.join(output)

def process_string(input):
    """
    Helper function to handle routine string processing

    Params:
        input   (str)       - the original string
        output  (str)       - the processed string
    """
    output = input.replace("\n", " ", )
    output = output.replace('"', "'")
    output = output.strip()
    return output


def process_template(input):
    """
    Helper function to apply some uniform processing
    to rendered templates

    Params:
        input   (str)       - the original string
        output  (str)       - the processed string
    """
    output = re.sub(r'\s*\w+\s+{\s+}', r'', input)
    # output = re.sub('    $', '', output, re.MULTILINE)
    return output


if __name__ == "__main__":
    main()

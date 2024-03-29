---
# generated by https://github.com/hashicorp/terraform-plugin-docs
page_title: "cloudtamerio_user_group Resource - terraform-provider-cloudtamerio"
subcategory: ""
description: |-
  
---

# Resource `cloudtamerio_user_group`





<!-- schema generated by tfplugindocs -->
## Schema

### Required

- **idms_id** (Number) ID of the IDMS where the user group is located.
- **name** (String) Name of the user group.

### Optional

- **description** (String) Description for the user group.
- **id** (String) The ID of this resource.
- **owner_groups** (Block List) (see [below for nested schema](#nestedblock--owner_groups)) List of group IDs that own the user group.
- **owner_users** (Block List) (see [below for nested schema](#nestedblock--owner_users)) List of user IDs that own the user group.
- **users** (Block List) (see [below for nested schema](#nestedblock--users)) IDs of the users in the user group.

### Read-only

- **created_at** (String) Date when the user was created.
- **enabled** (Boolean) Enabled state of the group.

<a id="nestedblock--owner_groups"></a>
### Nested Schema for `owner_groups`

Optional:

- **id** (Number) The ID of this resource.


<a id="nestedblock--owner_users"></a>
### Nested Schema for `owner_users`

Optional:

- **id** (Number) The ID of this resource.


<a id="nestedblock--users"></a>
### Nested Schema for `users`

Optional:

- **id** (Number) The ID of this resource.



package cloudtamerio

import (
	"fmt"

	hc "github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

// OUChanges allows moving an OU if the parent ID changes and updating permissions.
func OUChanges(c *hc.Client, d *schema.ResourceData, diags diag.Diagnostics, hasChanged int) (diag.Diagnostics, int) {
	// Handle OU move.
	if d.HasChanges("parent_ou_id") {
		hasChanged++
		arrParentOUID, _, _, err := hc.AssociationChangedInt(d, "parent_ou_id")
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to determine changeset for ParentOU on OrganizationalUnit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
			})
			return diags, hasChanged
		}
		_, err = c.POST(fmt.Sprintf("/v2/ou/%s/move", d.Id()), arrParentOUID)
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to add update Parent OU for Organizational Unit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
			})
			return diags, hasChanged
		}
	}

	// Handle associations.
	if d.HasChanges(
		"permission_scheme_id",
		"owner_user_group",
		"owner_user") {
		hasChanged++
		arrPermissionSchemaID, arrRemovePermissionSchemaID, _, err := hc.AssociationChangedInt(d, "permission_scheme_id")
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to add determining changeset for OrganizationalUnit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
			})
			return diags, hasChanged
		}

		arrAddOwnerUserGroupIds, arrRemoveOwnerUserGroupIds, _, err := hc.AssociationChanged(d, "owner_user_group")
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to add determining changeset for OrganizationalUnit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
			})
			return diags, hasChanged
		}

		arrAddOwnerUserID, arrRemoveOwnerUserID, _, err := hc.AssociationChanged(d, "owner_user")
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to add determining changeset for OrganizationalUnit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
			})
			return diags, hasChanged
		}

		if arrPermissionSchemaID != nil ||
			len(arrAddOwnerUserGroupIds) > 0 ||
			len(arrRemoveOwnerUserGroupIds) > 0 ||
			len(arrAddOwnerUserID) > 0 ||
			len(arrRemoveOwnerUserID) > 0 {
			_, err = c.POST(fmt.Sprintf("/v3/ou/%s/permission-mapping", d.Id()), hc.OUPermissionAdd{
				AppRoleID:         arrPermissionSchemaID,
				OwnerUserGroupIds: d.Get("owner_user").(*[]int),
				OwnerUserIds:      d.Get("owner_user_group").(*[]int),
			})
			if err != nil {
				diags = append(diags, diag.Diagnostic{
					Severity: diag.Error,
					Summary:  "Unable to add update Permission mapping for OrganizationalUnit",
					Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
				})
				return diags, hasChanged
			}
		}

		if arrRemovePermissionSchemaID != nil {
			// TODO: Figure how to patch/delete permissions schema changes
			err = nil
			if err != nil {
				diags = append(diags, diag.Diagnostic{
					Severity: diag.Error,
					Summary:  "Unable to remove owners on OrganizationalUnit",
					Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), d.Id()),
				})
				return diags, hasChanged
			}
		}
	}

	return diags, hasChanged
}

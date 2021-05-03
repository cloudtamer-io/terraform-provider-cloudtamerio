package cloudtamerio

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	hc "github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceOrganizationalUnit() *schema.Resource {
	return &schema.Resource{
		CreateContext: resourceOrganizationalUnitCreate,
		ReadContext:   resourceOrganizationalUnitRead,
		UpdateContext: resourceOrganizationalUnitUpdate,
		DeleteContext: resourceOrganizationalUnitDelete,
		Importer: &schema.ResourceImporter{
			StateContext: func(ctx context.Context, d *schema.ResourceData, m interface{}) ([]*schema.ResourceData, error) {
				resourceOrganizationalUnitRead(ctx, d, m)
				return []*schema.ResourceData{d}, nil
			},
		},
		Schema: map[string]*schema.Schema{
			"last_updated": {
				Type:     schema.TypeString,
				Optional: true,
				Computed: true,
			},
			"description": {
				Type:     schema.TypeString,
				Optional: true,
			},
			"name": {
				Type:     schema.TypeString,
				Optional: true,
			},
			"owner_user_groups": {
				Elem: &schema.Resource{
					Schema: map[string]*schema.Schema{
						"id": {
							Type:     schema.TypeInt,
							Optional: true,
						},
					},
				},
				Type:     schema.TypeList,
				Optional: true,
			},
			"owner_users": {
				Elem: &schema.Resource{
					Schema: map[string]*schema.Schema{
						"id": {
							Type:     schema.TypeInt,
							Optional: true,
						},
					},
				},
				Type:     schema.TypeList,
				Optional: true,
			},
			"parent_ou_id": {
				Type:     schema.TypeInt,
				Optional: true,
			},
			"permission_scheme_id": {
				Type:     schema.TypeInt,
				Optional: true,
			},
		},
	}
}

func resourceOrganizationalUnitCreate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)

	post := hc.OrganizationalUnitCreate{
		Name:               d.Get("name").(string),
		Description:        d.Get("description").(string),
		ParentOUID:         d.Get("parent_ou_id").(int),
		PermissionSchemeId: d.Get("permission_scheme_id").(int),
		OwnerUserGroupIds:  hc.FlattenGenericIDPointer(d, "owner_user_groups"),
		OwnerUserIds:       hc.FlattenGenericIDPointer(d, "owner_users"),
		PostWebhookID:      hc.FlattenIntPointer(d, "post_webhook_id"),
		PreWebhookID:       hc.FlattenIntPointer(d, "pre_webhook_id"),
	}

	resp, err := c.POST("/v3/ou", post)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to create OrganizationalUnit",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), post),
		})
		return diags
	} else if resp.RecordID == 0 {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to create OrganizationalUnit",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", errors.New("received item ID of 0"), post),
		})
		return diags
	}

	d.SetId(strconv.Itoa(resp.RecordID))

	resourceOrganizationalUnitRead(ctx, d, m)

	return diags
}

func resourceOrganizationalUnitRead(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)
	ID := d.Id()

	resp := new(hc.OrganizationalUnitResponse)
	err := c.GET(fmt.Sprintf("/v3/ou/%s", ID), resp)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			d.SetId("")
		} else {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to read Organizaitonal Unit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
		}
		return diags

	}
	item := resp.Data

	data := make(map[string]interface{})
	data["name"] = item.OU.Name
	data["description"] = item.OU.Description
	data["parent_ou_id"] = item.OU.ParentOUID
	data["owner_user_groups"] = make([]interface{}, 0)
	if hc.InflateObjectWithID(item.OwnerUserGroups) != nil {
		data["owner_user_groups"] = hc.InflateObjectWithID(item.OwnerUserGroups)
	}
	data["owner_users"] = make([]interface{}, 0)
	if hc.InflateObjectWithID(item.OwnerUsers) != nil {
		data["owner_users"] = hc.InflateObjectWithID(item.OwnerUsers)
	}
	if item.OU.PostWebhookID != nil {
		data["post_webhook_id"] = item.OU.PostWebhookID
	}
	if item.OU.PreWebhookID != nil {
		data["pre_webhook_id"] = item.OU.PreWebhookID
	}

	for k, v := range data {
		if err := d.Set(k, v); err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to read and set Organizational Unit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags
		}
	}

	return diags
}

func resourceOrganizationalUnitUpdate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)
	ID := d.Id()

	hasChanged := 0

	if d.HasChanges("description",
		"name",
		"post_webhook_id",
		"pre_webhook_id") {
		hasChanged++
		req := hc.OrganizationalUnitUpdate{
			Description:   d.Get("description").(string),
			Name:          d.Get("name").(string),
			PostWebhookID: hc.FlattenIntPointer(d, "post_webhook_id"),
			PreWebhookID:  hc.FlattenIntPointer(d, "pre_webhook_id"),
		}

		err := c.PATCH(fmt.Sprintf("/v3/ou/%s", ID), req)
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to update CloudRule",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags
		}
	}

	if d.HasChanges("parent_ou_id") {
		hasChanged++
		arrParentOUID, _, _, err := hc.AssociationChangedInt(d, "parent_ou_id")
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to determine changeset for ParentOU on OrganizationalUnit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags
		}
		_, err = c.POST(fmt.Sprintf("/v2/ou/%s/move", ID), arrParentOUID)
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to add update Parent OU for Organizational Unit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags
		}
	}

	// Handle associations.
	if d.HasChanges(
		"permission_scheme_id",
		"owner_user_group",
		"owner_user") {
		hasChanged++
		arrPermissionSchemaId, arrRemovePermissionSchemaId, _, err := hc.AssociationChangedInt(d, "permission_scheme_id")
		arrAddOwnerUserGroupIds, arrRemoveOwnerUserGroupIds, _, err := hc.AssociationChanged(d, "owner_user_group")
		arrAddOwnerUserId, arrRemoveOwnerUserId, _, err := hc.AssociationChanged(d, "owner_user")

		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to add determining changeset for OrganizationalUnit",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags
		}

		if arrPermissionSchemaId != nil ||
			len(arrAddOwnerUserGroupIds) > 0 ||
			len(arrRemoveOwnerUserGroupIds) > 0 ||
			len(arrAddOwnerUserId) > 0 ||
			len(arrRemoveOwnerUserId) > 0 {
			_, err = c.POST(fmt.Sprintf("/v3/ou/%s/permission-mapping", ID), hc.OrganizationalUnitPermissionAdd{
				AppRoleId:         arrPermissionSchemaId,
				OwnerUserGroupIds: d.Get("owner_user").(*[]int),
				OwnerUserIds:      d.Get("owner_user_group").(*[]int),
			})
			if err != nil {
				diags = append(diags, diag.Diagnostic{
					Severity: diag.Error,
					Summary:  "Unable to add update Permission mapping for Organizational Unit",
					Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
				})
				return diags
			}
		}

		if arrRemovePermissionSchemaId != nil {
			// TODO: Figure how to patch/delete permissions schema changes
			err = nil
			if err != nil {
				diags = append(diags, diag.Diagnostic{
					Severity: diag.Error,
					Summary:  "Unable to remove owners on CloudRule",
					Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
				})
				return diags
			}
		}
	}

	if hasChanged > 0 {
		d.Set("last_updated", time.Now().Format(time.RFC850))
	}

	return resourceOrganizationalUnitRead(ctx, d, m)
}

func resourceOrganizationalUnitDelete(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)
	ID := d.Id()

	err := c.DELETE(fmt.Sprintf("/v2/ou/%s", ID), nil)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to delete OrganizationalUnit",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
		})
		return diags
	}

	// d.SetId("") is automatically called assuming delete returns no errors, but
	// it is added here for explicitness.
	d.SetId("")

	return diags
}

package cloudtamerio

import (
	"context"
	"fmt"
	"strconv"
	"time"

	hc "github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func dataSourceSamlGroupAssociation() *schema.Resource {
	return &schema.Resource{
		ReadContext: dataSourceSamlGroupAssociationRead,
		Schema: map[string]*schema.Schema{
			"filter": {
				Type:     schema.TypeList,
				Optional: true,
				Elem: &schema.Resource{
					Schema: map[string]*schema.Schema{
						"name": {
							Type:     schema.TypeString,
							Required: true,
						},
						"values": {
							Type:     schema.TypeList,
							Required: true,
							Elem:     &schema.Schema{Type: schema.TypeString},
						},
						"regex": {
							Type:     schema.TypeBool,
							Optional: true,
							Default:  false,
						},
					},
				},
			},
			"list": {
				Type:     schema.TypeList,
				Computed: true,
				Elem: &schema.Resource{
					Schema: map[string]*schema.Schema{
						"assertion_name": {
							Type:     schema.TypeString,
							Computed: true,
						},
						"assertion_regex": {
							Type:     schema.TypeString,
							Computed: true,
						},
						"id": {
							Type:     schema.TypeInt,
							Computed: true,
						},
						"idms_id": {
							Type:     schema.TypeInt,
							Computed: true,
						},
						"idms_saml_id": {
							Type:     schema.TypeInt,
							Computed: true,
						},
						"should_update_on_login": {
							Type:     schema.TypeBool,
							Computed: true,
						},
						"user_group_id": {
							Type:     schema.TypeInt,
							Computed: true,
						},
					},
				},
			},
		},
	}
}

func dataSourceSamlGroupAssociationRead(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)

	resp := new(hc.GroupAssociationListResponse)
	err := c.GET("/v3/idms/{id}/group-association", resp)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to read SamlGroupAssociation",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), "all"),
		})
		return diags
	}

	f := hc.NewFilterable(d)

	arr := make([]map[string]interface{}, 0)
	for _, item := range resp.Data {
		data := make(map[string]interface{})
		data["assertion_name"] = item.AssertionName
		data["assertion_regex"] = item.AssertionRegex
		data["id"] = item.ID
		data["idms_id"] = item.IdmsID
		data["idms_saml_id"] = item.IdmsSamlID
		data["should_update_on_login"] = item.ShouldUpdateOnLogin
		data["user_group_id"] = item.UserGroupID

		match, err := f.Match(data)
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to filter SamlGroupAssociation",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), "filter"),
			})
			return diags
		} else if !match {
			continue
		}

		arr = append(arr, data)
	}

	if err := d.Set("list", arr); err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to read SamlGroupAssociation",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), "all"),
		})
		return diags
	}

	// Always run.
	d.SetId(strconv.FormatInt(time.Now().Unix(), 10))

	return diags
}

package cloudtamerio

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"

	hc "github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
	"github.com/mitchellh/mapstructure"
)

func resourceProject() *schema.Resource {
	return &schema.Resource{
		CreateContext: resourceProjectCreate,
		ReadContext:   resourceProjectRead,
		UpdateContext: resourceProjectUpdate,
		DeleteContext: resourceProjectDelete,
		Importer: &schema.ResourceImporter{
			StateContext: func(ctx context.Context, d *schema.ResourceData, m interface{}) ([]*schema.ResourceData, error) {
				resourceProjectRead(ctx, d, m)
				return []*schema.ResourceData{d}, nil
			},
		},
		Schema: map[string]*schema.Schema{
			// Notice there is no 'id' field specified because it will be created.
			"last_updated": {
				Type:     schema.TypeString,
				Optional: true,
				Computed: true,
			},
			"created_at": {
				Type:     schema.TypeString,
				Computed: true,
			},
			"auto_pay": {
				Type:     schema.TypeBool,
				Optional: true,
			},
			"default_aws_region": {
				Type:     schema.TypeString,
				Optional: true,
			},
			"description": {
				Type:     schema.TypeString,
				Optional: true,
			},
			"name": {
				Type:     schema.TypeString,
				Required: true,
			},
			"ou_id": {
				Type:     schema.TypeInt,
				Required: true,
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
				//ForceNew: true, // Not allowed to be changed, forces new item if changed.
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
				//ForceNew: true, // Not allowed to be changed, forces new item if changed.
			},
			"permission_scheme_id": {
				Type:     schema.TypeInt,
				Required: true,
				//ForceNew: true, // Not allowed to be changed, forces new item if changed.
			},
			"project_funding": {
				Elem: &schema.Resource{
					Schema: map[string]*schema.Schema{
						"amount": {
							Type:     schema.TypeInt,
							Optional: true,
						},
						"end_datecode": {
							Type:     schema.TypeString,
							Optional: true,
						},
						"funding_order": {
							Type:     schema.TypeInt,
							Optional: true,
						},
						// TODO: Change to Id
						"funding_source_id": {
							Type:     schema.TypeInt,
							Optional: true,
						},
						"start_datecode": {
							Type:     schema.TypeString,
							Optional: true,
						},
					},
				},
				Type:     schema.TypeList,
				Required: true,
			},
		},
	}
}

func resourceProjectCreate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)

	fundingInterface := d.Get("project_funding").([]interface{})
	log.Println(fmt.Sprintf("[TRACE] RAW Funding Value: %v", fundingInterface))
	fundingStruct := convertFundingInterfaceToStruct(fundingInterface)
	log.Println(fmt.Sprintf("[TRACE] Converted Funding Value: %v", fundingStruct))

	post := hc.ProjectCreate{
		AutoPay:            d.Get("auto_pay").(bool),
		DefaultAwsRegion:   d.Get("default_aws_region").(string),
		Description:        d.Get("description").(string),
		Name:               d.Get("name").(string),
		OUId:               d.Get("ou_id").(int),
		OwnerUserGroupIds:  hc.FlattenGenericIDPointer(d, "owner_user_groups"),
		OwnerUserIds:       hc.FlattenGenericIDPointer(d, "owner_users"),
		PermissionSchemeID: d.Get("permission_scheme_id").(int),
		ProjectFunding:     fundingStruct,
	}
	resp, err := c.POST("/v3/project", post)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to create Project",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), post),
		})
		return diags
	} else if resp.RecordID == 0 {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to create Project",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", errors.New("received item ID of 0"), post),
		})
		return diags
	}

	d.SetId(strconv.Itoa(resp.RecordID))

	resourceProjectRead(ctx, d, m)

	return diags
}

func Flatten(m map[string]interface{}) map[string]interface{} {
	o := map[string]interface{}{}
	for k, v := range m {
		switch child := v.(type) {
		case map[string]interface{}:
			nm := Flatten(child)
			for nk, nv := range nm {
				o[k+"."+nk] = nv
			}
		case []interface{}:
			for i := 0; i < len(child); i++ {
				o[k+"."+strconv.Itoa(i)] = child[i]
			}
		default:
			o[k] = v
		}
	}
	return o
}

func resourceProjectRead(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)
	ID := d.Id()

	resp := new(hc.ProjectResponse)
	err := c.GET(fmt.Sprintf("/v3/project/%s", ID), resp)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to read Project",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
		})
		return diags
	}
	item := resp.Data

	data := make(map[string]interface{})

	// Archived should be considered deleted as a resource type
	if item.Archived {
		d.SetId("")
		return diags
	}

	data["auto_pay"] = item.AutoPay
	data["default_aws_region"] = item.DefaultAwsRegion
	data["description"] = item.Description
	data["name"] = item.Name
	data["ou_id"] = item.OUId
	// TODO: After API Update Owner users, Owner User groups endpoints need to be added.
	// TODO: Determine if theres a v3 funding API, and how to flatten storing it

	for k, v := range data {
		if err := d.Set(k, v); err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to read and set Project",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags
		}
	}
	return diags
}

func resourceProjectUpdate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)

	hasChanged := 0
	diags, hasChanged = ProjectChanges(c, d, diags, hasChanged)
	if len(diags) > 0 {
		return diags
	}

	if hasChanged > 0 {
		d.Set("last_updated", time.Now().Format(time.RFC850))
	}

	return resourceProjectRead(ctx, d, m)
}

func resourceProjectDelete(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	var diags diag.Diagnostics
	c := m.(*hc.Client)
	ID := d.Id()

	err := c.DELETE(fmt.Sprintf("/v1/project/%s", ID), nil)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to delete project",
			Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
		})
		return diags
	}

	// d.SetId("") is automatically called assuming delete returns no errors, but
	// it is added here for explicitness.
	d.SetId("")

	return diags
}

func convertFundingInterfaceToStruct(input []interface{}) *[]hc.ProjectFundingCreate {
	var fundingStruct *[]hc.ProjectFundingCreate
	// TODO: Rewrite to have a key of ID and convert it to funding_source_id
	cfg := &mapstructure.DecoderConfig{
		Metadata: nil,
		Result:   &fundingStruct,
		TagName:  "json",
	}
	decoder, _ := mapstructure.NewDecoder(cfg)
	decoder.Decode(input)
	return fundingStruct
}

func ProjectChanges(c *hc.Client, d *schema.ResourceData, diags diag.Diagnostics, hasChanged int) (diag.Diagnostics, int) {
	// Determine if the attributes that are updatable are changed.
	ID := d.Id()
	if d.HasChanges(
		"description",
		"name",
		"auto_pay",
		"default_aws_region",
		"permission_scheme_id",
	) {
		hasChanged++
		req := hc.ProjectUpdatable{
			AutoPay:            d.Get("auto_pay").(bool),
			DefaultAwsRegion:   d.Get("default_aws_region").(string),
			Description:        d.Get("description").(string),
			Name:               d.Get("name").(string),
			PermissionSchemeID: d.Get("permission_scheme_id").(int),
		}

		err := c.PATCH(fmt.Sprintf("/v3/project/%s", ID), req)
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to update Project",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags, hasChanged
		}
	}
	if d.HasChanges(
		"project_funding",
	) {
		hasChanged++

		fundingInterface := d.Get("project_funding").([]interface{})
		log.Println(fmt.Sprintf("[TRACE] RAW Funding Value: %v", fundingInterface))
		fundingStruct := convertFundingInterfaceToStruct(fundingInterface)
		log.Println(fmt.Sprintf("[TRACE] Converted Funding Value: %v", fundingStruct))

		var fundingData []hc.ProjectFundingUpdatable
		for _, item := range *fundingStruct {
			endDate, _ := strconv.Atoi(strings.ReplaceAll(item.EndDatecode, "-", ""))
			startDate, _ := strconv.Atoi(strings.ReplaceAll(item.StartDatecode, "-", ""))
			update := hc.ProjectFundingUpdatable{
				Amount:          item.Amount,
				EndDatecode:     endDate,
				FundingOrder:    item.FundingOrder,
				FundingSourceId: item.FundingSourceId,
				StartDatecode:   startDate,
			}
			fundingData = append(fundingData, update)
		}
		err := c.PATCH(fmt.Sprintf("/v1/project/%s/funding", ID), fundingData)
		if err != nil {
			diags = append(diags, diag.Diagnostic{
				Severity: diag.Error,
				Summary:  "Unable to update Project",
				Detail:   fmt.Sprintf("Error: %v\nItem: %v", err.Error(), ID),
			})
			return diags, hasChanged
		}
	}

	// TODO: After API Update: Owner users, Owner User groups endpoints need to be added.
	return diags, hasChanged
}

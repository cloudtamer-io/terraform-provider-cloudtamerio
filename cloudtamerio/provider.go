// Package cloudtamerio provides the Terraform provider.
package cloudtamerio

import (
	"context"

	"github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

// Provider -
func Provider() *schema.Provider {
	return &schema.Provider{
		Schema: map[string]*schema.Schema{
			"url": {
				Description: "The URL of a cloudtamer.io installation. Example: https://cloudtamerio.example.com.",
				Type:        schema.TypeString,
				Required:    true,
				DefaultFunc: schema.EnvDefaultFunc("CLOUDTAMERIO_URL", nil),
			},
			"apikey": {
				Description: "The API key generated from cloudtamer.io. Example: app_1_XXXXXXXXXXXX.",
				Type:        schema.TypeString,
				Sensitive:   true,
				Required:    true,
				DefaultFunc: schema.EnvDefaultFunc("CLOUDTAMERIO_APIKEY", nil),
			},
			"skipsslvalidation": {
				Description: "If true, will skip SSL validation.",
				Type:        schema.TypeBool,
				Optional:    true,
				DefaultFunc: schema.EnvDefaultFunc("CLOUDTAMERIO_SKIPSSLVALIDATION", nil),
			},
		},
		ResourcesMap: map[string]*schema.Resource{
			"cloudtamerio_aws_cloudformation_template": resourceAwsCloudformationTemplate(),
			"cloudtamerio_aws_iam_policy":              resourceAwsIamPolicy(),
			"cloudtamerio_azure_policy":                resourceAzurePolicy(),
			"cloudtamerio_cloud_rule":                  resourceCloudRule(),
			"cloudtamerio_compliance_check":            resourceComplianceCheck(),
			"cloudtamerio_compliance_standard":         resourceComplianceStandard(),
			"cloudtamerio_ou_cloud_access_role":        resourceOUCloudAccessRole(),
			"cloudtamerio_project_cloud_access_role":   resourceProjectCloudAccessRole(),
			"cloudtamerio_ou":                          resourceOU(),
			"cloudtamerio_project":                     resourceProject(),
		},
		DataSourcesMap: map[string]*schema.Resource{
			"cloudtamerio_aws_cloudformation_template": dataSourceAwsCloudformationTemplate(),
			"cloudtamerio_aws_iam_policy":              dataSourceAwsIamPolicy(),
			"cloudtamerio_azure_policy":                dataSourceAzurePolicy(),
			"cloudtamerio_cloud_rule":                  dataSourceCloudRule(),
			"cloudtamerio_compliance_check":            dataSourceComplianceCheck(),
			"cloudtamerio_compliance_standard":         dataSourceComplianceStandard(),
			"cloudtamerio_ou":                          dataSourceOu(),
			"cloudtamerio_project":                     dataSourceProject(),
		},
		ConfigureContextFunc: providerConfigure,
	}
}

func providerConfigure(ctx context.Context, d *schema.ResourceData) (interface{}, diag.Diagnostics) {
	ctURL := d.Get("url").(string)
	ctAPIKey := d.Get("apikey").(string)

	// Warning or errors can be collected in a slice type
	var diags diag.Diagnostics

	var skipSSLValidation bool
	v, ok := d.GetOk("skipsslvalidation")
	if ok {
		t := v.(bool)
		skipSSLValidation = t
	}

	c := ctclient.NewClient(ctURL, ctAPIKey, skipSSLValidation)
	err := c.GET("/v3/me/cloud-access-role", nil)
	if err != nil {
		diags = append(diags, diag.Diagnostic{
			Severity: diag.Error,
			Summary:  "Unable to create cloudtamer.io client",
			Detail:   "Unable to authenticate - " + err.Error(),
		})

		return nil, diags
	}

	return c, diags
}

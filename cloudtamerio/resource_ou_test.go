package cloudtamerio

import (
	"fmt"
	"net/http"
	"strings"
	"testing"

	"github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	hc "github.com/cloudtamer-io/terraform-provider-cloudtamerio/cloudtamerio/internal/ctclient"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/resource"
	"github.com/hashicorp/terraform-plugin-sdk/v2/terraform"
)

const (
	ouResourceType = "cloudtamerio_ou"
	ouResourceName = "ou1"
)

// FIXME: Move these into a different file (e.g. helper.go or resource_user_test.go).
//
// I feel like we should be creating a User & User Group instead of assuming
// "Admin" & "Administrators" exist since they can be deleted.
var (
	ownerUserIds      = []int{1}
	ownerUserGroupIDs = []int{1}
)

func TestAccResourceOU(t *testing.T) {
	ou := hc.OUCreate{
		Name:               "Terraform AccTest OU",
		Description:        "sample OU for terraform acceptance test",
		ParentOuID:         0,
		PermissionSchemeID: 2,
		OwnerUserIds:       &ownerUserIds,
		OwnerUserGroupIds:  &ownerUserGroupIDs,
	}

	// Create
	create := resource.TestStep{
		Config: testAccOUGenerateResourceDeclaration(&ou),
		Check:  resource.ComposeTestCheckFunc(testAccOUCheckResource(&ou)...),
	}

	// Update
	ou.Name = "(Updated) Terraform AccTest OU"
	ou.Description = "(Updated) sample OU for terraform acceptance test"
	update := resource.TestStep{
		Config: testAccOUGenerateResourceDeclaration(&ou),
		Check:  resource.ComposeTestCheckFunc(testAccOUCheckResource(&ou)...),
	}

	// Remove Owner User
	ou.OwnerUserIds = nil
	removeOwnerUser := resource.TestStep{
		Config: testAccOUGenerateResourceDeclaration(&ou),
		Check:  resource.ComposeTestCheckFunc(testAccOUCheckResource(&ou)...),
	}

	// Add Owner User
	ou.OwnerUserIds = &ownerUserIds
	addOwnerUser := resource.TestStep{
		Config: testAccOUGenerateResourceDeclaration(&ou),
		Check:  resource.ComposeTestCheckFunc(testAccOUCheckResource(&ou)...),
	}

	// Remove Owner User Group
	ou.OwnerUserGroupIds = nil
	removeOwnerUGroup := resource.TestStep{
		Config: testAccOUGenerateResourceDeclaration(&ou),
		Check:  resource.ComposeTestCheckFunc(testAccOUCheckResource(&ou)...),
	}

	// Add Owner User Group
	ou.OwnerUserGroupIds = &ownerUserGroupIDs
	addOwnerUGroup := resource.TestStep{
		Config: testAccOUGenerateResourceDeclaration(&ou),
		Check:  resource.ComposeTestCheckFunc(testAccOUCheckResource(&ou)...),
	}

	resource.Test(t, resource.TestCase{
		PreCheck:     func() { testAccPreCheck(t) },
		Providers:    testAccProviders,
		CheckDestroy: testAccOUCheckResourceDestroy,
		Steps: []resource.TestStep{
			create,
			update,
			removeOwnerUser,
			addOwnerUser,
			removeOwnerUGroup,
			addOwnerUGroup,
		},
	})
}

// testAccOUCheckResource returns a slice of functions that validate the test resource's fields
func testAccOUCheckResource(ou *hc.OUCreate) (funcs []resource.TestCheckFunc) {
	funcs = []resource.TestCheckFunc{
		resource.TestCheckResourceAttr(ouResourceType+"."+ouResourceName, "name", ou.Name),
		resource.TestCheckResourceAttr(ouResourceType+"."+ouResourceName, "description", ou.Description),
		resource.TestCheckResourceAttr(ouResourceType+"."+ouResourceName, "parent_ou_id", fmt.Sprint(ou.ParentOuID)),
		resource.TestCheckResourceAttr(ouResourceType+"."+ouResourceName, "permission_scheme_id", fmt.Sprint(ou.PermissionSchemeID)),
	}

	funcs = append(funcs, hc.GenerateAccTestChecksForResourceOwners(
		ouResourceType,
		ouResourceName,
		ou.OwnerUserIds,
		ou.OwnerUserGroupIds,
	)...)

	return
}

// testAccOUGenerateResourceDeclaration generates a resource declaration string (a la main.tf)
func testAccOUGenerateResourceDeclaration(ou *hc.OUCreate) string {
	if ou == nil {
		return ""
	}

	// Required fields
	return fmt.Sprintf(`
		resource "%v" "%v" {
			name                 = "%v"
			description          = "%v"
			parent_ou_id         = %v
			permission_scheme_id = %v
			%v
		}`,
		ouResourceType, ouResourceName,
		ou.Name,
		ou.Description,
		ou.ParentOuID,
		ou.PermissionSchemeID,
		hc.GenerateOwnerClausesForResourceTest(ou.OwnerUserIds, ou.OwnerUserGroupIds),
	)
}

// testAccOUCheckResourceDestroy verifies the resource has been destroyed
func testAccOUCheckResourceDestroy(s *terraform.State) error {
	// retrieve the connection established in Provider configuration
	meta := testAccProvider.Meta()
	if meta == nil {
		return nil
	}

	c := meta.(*ctclient.Client)

	// loop through the resources in state, verifying each resource is destroyed
	for _, rs := range s.RootModule().Resources {
		if rs.Type != ouResourceType {
			continue
		}

		// Retrieve our resource by referencing it's state ID for API lookup
		resp := new(hc.OUResponse)
		err := c.GET(fmt.Sprintf("/v3/ou/%s", rs.Primary.ID), resp)
		if err == nil {
			if fmt.Sprint(resp.Data.OU.ID) == rs.Primary.ID {
				return fmt.Errorf("OU (%s) still exists.", rs.Primary.ID)
			}

			return nil
		}

		// If the error is equivalent to 404 not found, the resource is destroyed.
		// Otherwise, return the error
		if !strings.Contains(err.Error(), fmt.Sprintf("status: %d", http.StatusNotFound)) {
			return err
		}
	}

	return nil
}

package ctclient

// OrganizationalUnitListResponse for: GET /api/v3/ou
type OrganizationalUnitListResponse struct {
	Data []struct {
		CreatedAt     string `json:"created_at"`
		Description   string `json:"description"`
		ID            int    `json:"id"`
		Name          string `json:"name"`
		PostWebhookID *int   `json:"post_webhook_id"`
		PreWebhookID  *int   `json:"pre_webhook_id"`
	} `json:"data"`
	Status int `json:"status"`
}

// CloudRuleResponse for: GET /api/v3/ou/{id}
type OrganizationalUnitResponse struct {
	Data struct {
		OU struct {
			CreatedAt     string `json:"created_at"`
			Description   string `json:"description"`
			ID            int    `json:"id"`
			Name          string `json:"name"`
			ParentOUID    int    `json:"parent_ou_id"`
			PostWebhookID *int   `json:"post_webhook_id"`
			PreWebhookID  *int   `json:"pre_webhook_id"`
		} `json:"ou"`
		OwnerUserGroups []ObjectWithID `json:"owner_user_groups"`
		OwnerUsers      []ObjectWithID `json:"owner_users"`
	} `json:"data"`
	Status int `json:"status"`
}

// OrganizationalUnitCreate for: POST /api/v3/ou
type OrganizationalUnitCreate struct {
	Description        string `json:"description"`
	Name               string `json:"name"`
	OwnerUserGroupIds  *[]int `json:"owner_user_group_ids"`
	OwnerUserIds       *[]int `json:"owner_user_ids"`
	ParentOUID         int    `json:"parent_ou_id"`
	PermissionSchemeId int    `json:"permission_scheme_id"`
	PostWebhookID      *int   `json:"post_webhook_id"`
	PreWebhookID       *int   `json:"pre_webhook_id"`
}

// OrganizationalUnitUpdate for: PATCH /api/v3/ou/{id}
type OrganizationalUnitUpdate struct {
	Description   string `json:"description"`
	Name          string `json:"name"`
	PostWebhookID *int   `json:"post_webhook_id"`
	PreWebhookID  *int   `json:"pre_webhook_id"`
}

type OrganizationalUnitPermissionAdd struct {
	AppRoleId         *int   `json:"app_role_id"`
	OwnerUserGroupIds *[]int `json:"user_groups_ids"`
	OwnerUserIds      *[]int `json:"user_ids"`
	PostWebhookID     *int   `json:"post_webhook_id"`
	PreWebhookID      *int   `json:"pre_webhook_id"`
}

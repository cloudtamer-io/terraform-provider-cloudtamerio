package ctclient

type ProjectFundingCreate struct {
	Amount          int    `json:"amount"`
	EndDatecode     string `json:"end_datecode"`
	FundingOrder    int    `json:"funding_order"`
	FundingSourceId int    `json:"funding_source_id"`
	StartDatecode   string `json:"start_datecode"`
}

// ProjectFundingUpdatable: POST /api/v1/project/{id}/funding
type ProjectFundingUpdatable struct {
	Amount          int `json:"amount"`
	EndDatecode     int `json:"end_datecode"`
	FundingOrder    int `json:"funding_order"`
	FundingSourceId int `json:"funding_source_id"`
	StartDatecode   int `json:"start_datecode"`
}

// ProjectCreate for: POST /api/v3/project
type ProjectCreate struct {
	AutoPay            bool                    `json:"auto_pay"`
	DefaultAwsRegion   string                  `json:"default_aws_region"`
	Description        string                  `json:"description"`
	Name               string                  `json:"name"`
	OUId               int                     `json:"ou_id"`
	OwnerUserGroupIds  *[]int                  `json:"owner_user_group_ids"`
	OwnerUserIds       *[]int                  `json:"owner_user_ids"`
	PermissionSchemeID int                     `json:"permission_scheme_id"`
	ProjectFunding     *[]ProjectFundingCreate `json:"project_funding"`
}

// ProjectResponse for: GET /api/v3/project/{id}
type ProjectResponse struct {
	Data struct {
		Archived         bool   `json:"archived"`
		AutoPay          bool   `json:"auto_pay"`
		DefaultAwsRegion string `json:"default_aws_region"`
		Description      string `json:"description"`
		Id               int    `json:"id"`
		Name             string `json:"name"`
		OUId             int    `json:"ou_id"`
	} `json:"data"`
	Status int `json:"status"`
}

type ProjectFundingResponse struct {
	Data []struct {
		Amount        int `json:"planned_for_project"`
		StartDatecode int `json:"start_datecode"`
		EndDatecode   int `json:"end_datecode"`
		FindingSource struct {
			FundingSourceId int `json:"id"`
		} `json:"funding_source"`
	} `json:"data"`
	Status int `json:"status"`
}

// ProjectUpdatable for: PATCH /api/v3/project/{id}
type ProjectUpdatable struct {
	AutoPay            bool   `json:"auto_pay"`
	DefaultAwsRegion   string `json:"default_aws_region"`
	Description        string `json:"description"`
	Name               string `json:"name"`
	PermissionSchemeID int    `json:"permission_scheme_id"`
}

// ProjectListResponse for: GET /api/v3/project
type ProjectListResponse struct {
	Data []struct {
		AutoPay          bool   `json:"auto_pay"`
		DefaultAwsRegion string `json:"default_aws_region"`
		Description      string `json:"description"`
		Id               int    `json:"id"`
		Name             string `json:"name"`
		OUId             int    `json:"ou_id"`
	}
	Status int `json:"status"`
}

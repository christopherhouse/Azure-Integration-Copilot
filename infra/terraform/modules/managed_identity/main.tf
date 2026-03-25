module "user_assigned_identity" {
  source  = "Azure/avm-res-managedidentity-userassignedidentity/azurerm"
  version = "0.5.0"

  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  enable_telemetry    = false
  tags                = var.tags

  role_assignments = var.role_assignments
}

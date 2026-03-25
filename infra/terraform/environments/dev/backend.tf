terraform {
  backend "azurerm" {
    resource_group_name  = "RG-CUS-DEPLOYMENT"
    storage_account_name = "sacustfdeploy"
    container_name       = "tfstate"
    key                  = "dev/aic/aic-dev.tfstate"
    use_azuread_auth     = true
  }
}

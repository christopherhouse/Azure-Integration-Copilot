terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-aic"
    storage_account_name = "sttfstateaicprod"
    container_name       = "tfstate"
    key                  = "aic-prod.tfstate"
    use_azuread_auth     = true
  }
}

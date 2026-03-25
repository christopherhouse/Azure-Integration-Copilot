terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-aic"
    storage_account_name = "sttfstateaicdev"
    container_name       = "tfstate"
    key                  = "aic-dev.tfstate"
    use_azuread_auth     = true
  }
}

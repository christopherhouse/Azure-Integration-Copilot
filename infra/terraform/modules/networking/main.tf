data "azurerm_resource_group" "this" {
  name = var.resource_group_name
}

# ---------------------------------------------------------------------------
# Network Security Groups — raw azurerm resources; IDs are passed into the
# AVM VNet module's subnet definitions so NSG associations are handled by
# the REST API via azapi_resource (no separate association resources needed).
# ---------------------------------------------------------------------------

resource "azurerm_network_security_group" "container_apps" {
  name                = "nsg-container-apps-${var.vnet_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_network_security_group" "app_gateway" {
  name                = "nsg-app-gateway-${var.vnet_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  # Required for Application Gateway v2 infrastructure health communication
  security_rule {
    name                       = "Allow-GatewayManager-Inbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "65200-65535"
    source_address_prefix      = "GatewayManager"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Allow-AzureLoadBalancer-Inbound"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Allow-HTTP-Inbound"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Allow-HTTPS-Inbound"
    priority                   = 210
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_security_group" "private_endpoints" {
  name                = "nsg-private-endpoints-${var.vnet_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_network_security_group" "integration" {
  name                = "nsg-integration-${var.vnet_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# Virtual Network + subnets — AVM manages subnets and NSG associations
# ---------------------------------------------------------------------------

module "vnet" {
  source  = "Azure/avm-res-network-virtualnetwork/azurerm"
  version = "0.17.1"

  name             = var.vnet_name
  location         = var.location
  parent_id        = data.azurerm_resource_group.this.id
  address_space    = toset(var.vnet_address_space)
  enable_telemetry = false
  tags             = var.tags

  subnets = {
    "snet-container-apps" = {
      name           = "snet-container-apps"
      address_prefix = var.subnet_container_apps_prefix
      network_security_group = {
        id = azurerm_network_security_group.container_apps.id
      }
      delegations = [{
        name = "Microsoft.App.environments"
        service_delegation = {
          name = "Microsoft.App/environments"
        }
      }]
    }
    "snet-private-endpoints" = {
      name           = "snet-private-endpoints"
      address_prefix = var.subnet_private_endpoints_prefix
      network_security_group = {
        id = azurerm_network_security_group.private_endpoints.id
      }
    }
    "snet-integration" = {
      name           = "snet-integration"
      address_prefix = var.subnet_integration_prefix
      network_security_group = {
        id = azurerm_network_security_group.integration.id
      }
    }
    "snet-app-gateway" = {
      name           = "snet-app-gateway"
      address_prefix = var.subnet_app_gateway_prefix
      network_security_group = {
        id = azurerm_network_security_group.app_gateway.id
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Private DNS Zones — one AVM module instance per zone, linked to the VNet
# ---------------------------------------------------------------------------

locals {
  private_dns_zones = [
    "privatelink.vaultcore.azure.net",
    "privatelink.blob.core.windows.net",
    "privatelink.queue.core.windows.net",
    "privatelink.table.core.windows.net",
    "privatelink.documents.azure.com",
    "privatelink.servicebus.windows.net",
    "privatelink.azurecr.io",
    "privatelink.webpubsub.azure.com",
  ]
}

module "private_dns_zones" {
  source   = "Azure/avm-res-network-privatednszone/azurerm"
  version  = "0.5.0"
  for_each = toset(local.private_dns_zones)

  domain_name      = each.value
  parent_id        = data.azurerm_resource_group.this.id
  enable_telemetry = false
  tags             = var.tags

  virtual_network_links = {
    "link-${replace(each.value, ".", "-")}" = {
      vnetlinkname = "link-${replace(each.value, ".", "-")}"
      vnetid       = module.vnet.resource_id
    }
  }
}

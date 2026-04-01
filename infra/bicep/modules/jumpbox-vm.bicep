// ---------------------------------------------------------------------------
// Jumpbox VM — Windows Server 2022, no public IP, Bastion-only access
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the virtual machine')
param vmName string

@description('Resource ID of the jumpbox subnet')
param subnetJumpboxId string

@description('Admin username for the VM')
param adminUsername string

@secure()
@description('Admin password for the VM')
param adminPassword string

@description('Tags to apply')
param tags object = {}

// ---------------------------------------------------------------------------
// Windows Jumpbox VM — AVM
// ---------------------------------------------------------------------------

module jumpboxVm 'br/public:avm/res/compute/virtual-machine:0.22.0' = {
  name: 'vm-${uniqueString(vmName)}'
  params: {
    name: vmName
    location: location
    enableTelemetry: false
    tags: tags

    // OS configuration
    osType: 'Windows'
    vmSize: 'Standard_D2s_v5'
    availabilityZone: -1

    // Image — Windows Server 2022 Datacenter Azure Edition
    imageReference: {
      publisher: 'MicrosoftWindowsServer'
      offer: 'WindowsServer'
      sku: '2022-datacenter-azure-edition'
      version: 'latest'
    }

    // OS disk
    osDisk: {
      caching: 'ReadWrite'
      diskSizeGB: 128
      managedDisk: {
        storageAccountType: 'Standard_LRS'
      }
    }

    // Authentication
    adminUsername: adminUsername
    adminPassword: adminPassword

    // NIC — no public IP, connected to jumpbox subnet only
    nicConfigurations: [
      {
        nicSuffix: '-nic-01'
        ipConfigurations: [
          {
            name: 'ipconfig01'
            subnetResourceId: subnetJumpboxId
          }
        ]
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the jumpbox VM')
output vmId string = jumpboxVm.outputs.resourceId

@description('Name of the jumpbox VM')
output vmName string = jumpboxVm.outputs.name

// ---------------------------------------------------------------------------
// Integrisight.ai Operations Workbook — single-pane-of-glass monitoring
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Display name for the workbook')
param workbookDisplayName string

@description('Resource ID of the Log Analytics workspace')
param logAnalyticsWorkspaceId string

@description('Resource ID of the Application Insights instance')
param applicationInsightsResourceId string

@description('Common resource tags')
param tags object = {}

// ---------------------------------------------------------------------------
// Workbook JSON template — placeholders are replaced at deploy time
// ---------------------------------------------------------------------------
#disable-next-line prefer-interpolation
var workbookJsonTemplate = '''
{
  "version": "Notebook/1.0",
  "items": [
    {
      "type": 9,
      "content": {
        "version": "KqlParameterItem/1.0",
        "parameters": [
          {
            "id": "par-timerange",
            "version": "KqlParameterItem/1.0",
            "name": "TimeRange",
            "type": 4,
            "isRequired": true,
            "value": {
              "durationMs": 86400000
            },
            "typeSettings": {
              "selectableValues": [
                {
                  "durationMs": 300000
                },
                {
                  "durationMs": 900000
                },
                {
                  "durationMs": 1800000
                },
                {
                  "durationMs": 3600000
                },
                {
                  "durationMs": 14400000
                },
                {
                  "durationMs": 43200000
                },
                {
                  "durationMs": 86400000
                },
                {
                  "durationMs": 172800000
                },
                {
                  "durationMs": 604800000
                }
              ]
            },
            "label": "Time Range"
          },
          {
            "id": "par-subscription",
            "version": "KqlParameterItem/1.0",
            "name": "Subscription",
            "type": 6,
            "isRequired": true,
            "multiSelect": false,
            "typeSettings": {
              "additionalResourceOptions": [
                "value::1"
              ],
              "includeAll": false,
              "showDefault": false
            },
            "defaultValue": "value::1",
            "label": "Subscription"
          },
          {
            "id": "par-loganalyticsworkspace",
            "version": "KqlParameterItem/1.0",
            "name": "LogAnalyticsWorkspace",
            "type": 5,
            "isRequired": true,
            "query": "Resources | where type == \"microsoft.operationalinsights/workspaces\" | project value = id, label = name | order by label asc",
            "crossComponentResources": [
              "{Subscription}"
            ],
            "typeSettings": {
              "additionalResourceOptions": [],
              "resourceTypeFilter": {
                "microsoft.operationalinsights/workspaces": true
              }
            },
            "value": "__LOG_ANALYTICS_ID__",
            "queryType": 1,
            "label": "Log Analytics Workspace"
          },
          {
            "id": "par-applicationinsights",
            "version": "KqlParameterItem/1.0",
            "name": "ApplicationInsights",
            "type": 5,
            "isRequired": true,
            "query": "Resources | where type == \"microsoft.insights/components\" | project value = id, label = name | order by label asc",
            "crossComponentResources": [
              "{Subscription}"
            ],
            "typeSettings": {
              "additionalResourceOptions": [],
              "resourceTypeFilter": {
                "microsoft.insights/components": true
              }
            },
            "value": "__APP_INSIGHTS_ID__",
            "queryType": 1,
            "label": "Application Insights"
          },
          {
            "id": "par-resourcegroupname",
            "version": "KqlParameterItem/1.0",
            "name": "ResourceGroupName",
            "type": 5,
            "isRequired": true,
            "query": "Resources | where type =~ \"microsoft.operationalinsights/workspaces\" or type =~ \"microsoft.insights/components\" or type =~ \"microsoft.app/containerapps\" | project resourceGroup | distinct resourceGroup | project value = resourceGroup, label = resourceGroup | order by label asc",
            "crossComponentResources": [
              "{Subscription}"
            ],
            "typeSettings": {
              "additionalResourceOptions": []
            },
            "queryType": 1,
            "value": "__RESOURCE_GROUP__",
            "label": "Resource Group"
          },
          {
            "id": "par-selectedtab",
            "version": "KqlParameterItem/1.0",
            "name": "selectedTab",
            "type": 1,
            "isRequired": false,
            "isHiddenWhenLocked": true,
            "criteriaData": [
              {
                "criteriaContext": {
                  "operator": "Default",
                  "resultValType": "static",
                  "resultVal": "tab1"
                }
              }
            ]
          }
        ],
        "style": "pills",
        "queryType": 0
      },
      "name": "globalParameters"
    },
    {
      "type": 11,
      "content": {
        "version": "LinkItem/1.0",
        "style": "tabs",
        "links": [
          {
            "id": "lt1",
            "cellValue": "tab1",
            "linkTarget": "parameter",
            "linkLabel": "Platform Health Overview",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "Platform Health Overview",
            "isDefault": true
          },
          {
            "id": "lt2",
            "cellValue": "tab2",
            "linkTarget": "parameter",
            "linkLabel": "API & Frontend Performance",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "API & Frontend Performance"
          },
          {
            "id": "lt3",
            "cellValue": "tab3",
            "linkTarget": "parameter",
            "linkLabel": "Worker Pipeline",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "Worker Pipeline"
          },
          {
            "id": "lt4",
            "cellValue": "tab4",
            "linkTarget": "parameter",
            "linkLabel": "Data Services",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "Data Services"
          },
          {
            "id": "lt5",
            "cellValue": "tab5",
            "linkTarget": "parameter",
            "linkLabel": "Networking & Security",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "Networking & Security"
          },
          {
            "id": "lt6",
            "cellValue": "tab6",
            "linkTarget": "parameter",
            "linkLabel": "Tenant Activity",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "Tenant Activity"
          },
          {
            "id": "lt7",
            "cellValue": "tab7",
            "linkTarget": "parameter",
            "linkLabel": "End-to-End Transaction Search",
            "subTarget": "selectedTab",
            "style": "link",
            "preText": "End-to-End Transaction Search"
          }
        ]
      },
      "name": "tabNavigation"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "resources\n| where resourceGroup == \"{ResourceGroupName}\"\n| where type in~ (\"microsoft.documentdb/databaseaccounts\",\"microsoft.storage/storageaccounts\",\"microsoft.eventgrid/namespaces\",\"microsoft.signalrservice/webpubsub\",\"microsoft.keyvault/vaults\",\"microsoft.containerregistry/registries\",\"microsoft.app/managedenvironments\",\"microsoft.cdn/profiles\",\"microsoft.cognitiveservices/accounts\",\"microsoft.network/bastionhosts\")\n| project ResourceName=name, ResourceType=type, HealthStatus=properties.provisioningState, Location=location",
              "size": 0,
              "title": "Resource Health Grid",
              "queryType": 1,
              "resourceType": "microsoft.resourcegraph/resources",
              "crossComponentResources": [
                "{Subscription}"
              ],
              "visualization": "grid",
              "gridSettings": {
                "formatters": [
                  {
                    "columnMatch": "HealthStatus",
                    "formatter": 18,
                    "formatOptions": {
                      "thresholdsOptions": "icons",
                      "thresholdsGrid": [
                        {
                          "operator": "==",
                          "thresholdValue": "Failed",
                          "representation": "4",
                          "text": "{0}"
                        },
                        {
                          "operator": "==",
                          "thresholdValue": "Updating",
                          "representation": "2",
                          "text": "{0}"
                        },
                        {
                          "operator": "Default",
                          "representation": "success",
                          "text": "{0}"
                        }
                      ]
                    }
                  }
                ]
              }
            },
            "name": "resourceHealthGrid"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "resources\n| where type == \"microsoft.app/containerapps\"\n| where resourceGroup == \"{ResourceGroupName}\"\n| project AppName=name, ProvisioningState=properties.provisioningState, ActiveRevision=properties.latestRevisionName, Location=location",
              "size": 0,
              "title": "Container Apps Status",
              "queryType": 1,
              "resourceType": "microsoft.resourcegraph/resources",
              "crossComponentResources": [
                "{Subscription}"
              ],
              "visualization": "grid"
            },
            "name": "containerAppsStatus"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AlertsManagementResources\n| where type == \"microsoft.alertsmanagement/alerts\"\n| where properties.essentials.monitorCondition == \"Fired\"\n| project AlertName=properties.essentials.alertRule, Severity=properties.essentials.severity, Target=properties.essentials.targetResourceName, FiredTime=properties.essentials.startDateTime\n| order by FiredTime desc",
              "size": 0,
              "title": "Active Alerts Summary",
              "queryType": 1,
              "resourceType": "microsoft.resourcegraph/resources",
              "crossComponentResources": [
                "{Subscription}"
              ],
              "visualization": "grid"
            },
            "name": "activeAlerts"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} | summarize error_rate = round(1.0 * countif(toint(resultCode) >= 500) / count() * 100, 2) | project ['Error Rate %'] = error_rate",
              "size": 4,
              "title": "Error Rate",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "tiles",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ],
              "tileSettings": {
                "showBorder": true,
                "titleContent": {
                  "columnMatch": "Error Rate %",
                  "formatter": 1
                },
                "leftContent": {
                  "columnMatch": "Error Rate %",
                  "formatter": 18,
                  "formatOptions": {
                    "thresholdsOptions": "colors",
                    "thresholdsGrid": [
                      {
                        "operator": "<",
                        "thresholdValue": "1",
                        "representation": "green",
                        "text": "{0}{1}"
                      },
                      {
                        "operator": "<",
                        "thresholdValue": "5",
                        "representation": "yellow",
                        "text": "{0}{1}"
                      },
                      {
                        "operator": "Default",
                        "representation": "redBright",
                        "text": "{0}{1}"
                      }
                    ]
                  }
                }
              }
            },
            "name": "errorRateTile"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where cloud_RoleName == \"api\" and timestamp {TimeRange} | summarize ['P95 Latency (ms)'] = round(percentile(duration, 95), 0)",
              "size": 4,
              "title": "API P95 Latency",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "tiles",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ],
              "tileSettings": {
                "showBorder": true,
                "titleContent": {
                  "columnMatch": "P95 Latency (ms)",
                  "formatter": 1
                },
                "leftContent": {
                  "columnMatch": "P95 Latency (ms)",
                  "formatter": 18,
                  "formatOptions": {
                    "thresholdsOptions": "colors",
                    "thresholdsGrid": [
                      {
                        "operator": "<",
                        "thresholdValue": "500",
                        "representation": "green",
                        "text": "{0}{1}"
                      },
                      {
                        "operator": "<",
                        "thresholdValue": "2000",
                        "representation": "yellow",
                        "text": "{0}{1}"
                      },
                      {
                        "operator": "Default",
                        "representation": "redBright",
                        "text": "{0}{1}"
                      }
                    ]
                  }
                }
              }
            },
            "name": "p95LatencyTile"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.EVENTGRID\" and Category == \"DeliveryFailures\" and TimeGenerated {TimeRange} | summarize ['Dead Letters'] = count()",
              "size": 4,
              "title": "Dead-Letter Count",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "tiles",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ],
              "tileSettings": {
                "showBorder": true,
                "titleContent": {
                  "columnMatch": "Dead Letters",
                  "formatter": 1
                },
                "leftContent": {
                  "columnMatch": "Dead Letters",
                  "formatter": 18,
                  "formatOptions": {
                    "thresholdsOptions": "colors",
                    "thresholdsGrid": [
                      {
                        "operator": "==",
                        "thresholdValue": "0",
                        "representation": "green",
                        "text": "{0}{1}"
                      },
                      {
                        "operator": "Default",
                        "representation": "redBright",
                        "text": "{0}{1}"
                      }
                    ]
                  }
                }
              }
            },
            "name": "deadLetterTile"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} | extend tid = tostring(customDimensions.tenantId) | where isnotempty(tid) | summarize ['Active Tenants'] = dcount(tid)",
              "size": 4,
              "title": "Active Tenants",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "tiles",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ],
              "tileSettings": {
                "showBorder": true,
                "titleContent": {
                  "columnMatch": "Active Tenants",
                  "formatter": 1
                },
                "leftContent": {
                  "columnMatch": "Active Tenants",
                  "formatter": 12,
                  "formatOptions": {
                    "palette": "blue"
                  },
                  "numberFormat": {
                    "unit": 17,
                    "options": {
                      "style": "decimal",
                      "maximumFractionDigits": 0
                    }
                  }
                }
              }
            },
            "name": "activeTenantsTile"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab1"
      },
      "name": "tab1Group"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} | summarize Count = count() by bin(timestamp, 5m), cloud_RoleName | render timechart",
              "size": 0,
              "title": "Request Volume",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "timechart",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "requestVolume"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} | extend StatusBucket = case(toint(resultCode) < 300, \"2xx\", toint(resultCode) < 400, \"3xx\", toint(resultCode) < 500, \"4xx\", \"5xx\") | summarize Count = count() by bin(timestamp, 5m), StatusBucket | render areachart",
              "size": 0,
              "title": "Response Status Distribution",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "unstackedbar",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "responseStatusDist"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} and cloud_RoleName == \"api\" | summarize P50 = percentile(duration, 50), P95 = percentile(duration, 95), P99 = percentile(duration, 99) by bin(timestamp, 5m) | render timechart",
              "size": 0,
              "title": "Latency Percentiles",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "timechart",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "latencyPercentiles"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} and cloud_RoleName == \"api\" | summarize P95 = percentile(duration, 95), Requests = count(), Errors = countif(toint(resultCode) >= 500) by Endpoint = name | top 10 by P95 desc",
              "size": 0,
              "title": "Slowest Endpoints",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "slowestEndpoints"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} and success == false | project Timestamp = timestamp, Endpoint = name, Status = resultCode, Duration = duration, OperationId = operation_Id | order by Timestamp desc | take 100",
              "size": 0,
              "title": "Failed Requests Detail",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "failedRequestsDetail"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where Category == \"FrontDoorAccessLog\" and TimeGenerated {TimeRange} | summarize RequestCount = count(), P95Latency = percentile(todouble(timeTaken_s), 95) by bin(TimeGenerated, 5m) | render timechart",
              "size": 0,
              "title": "Front Door Metrics",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "frontDoorMetrics"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab2"
      },
      "name": "tab2Group"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "customEvents | where timestamp {TimeRange} | where name in (\"ArtifactUploaded\", \"ArtifactScanPassed\", \"ArtifactParsed\", \"GraphUpdated\", \"AnalysisCompleted\") | summarize Count = count() by Stage = name | order by case(Stage == \"ArtifactUploaded\", 1, Stage == \"ArtifactScanPassed\", 2, Stage == \"ArtifactParsed\", 3, Stage == \"GraphUpdated\", 4, Stage == \"AnalysisCompleted\", 5, 6)",
              "size": 0,
              "title": "Pipeline Funnel",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "barchart",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "pipelineFunnel"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "customMetrics | where timestamp {TimeRange} | where name in (\"parse_duration_seconds\", \"graph_build_duration_seconds\", \"analysis_duration_seconds\", \"notification_duration_seconds\") | summarize P50 = percentile(value, 50), P95 = percentile(value, 95), P99 = percentile(value, 99) by Worker = name",
              "size": 0,
              "title": "Worker Processing Duration",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "workerDuration"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.EVENTGRID\" and TimeGenerated {TimeRange} | summarize DeliverySuccess = countif(Category == \"DeliverySuccesses\"), DeliveryFailure = countif(Category == \"DeliveryFailures\") by bin(TimeGenerated, 5m) | render timechart",
              "size": 0,
              "title": "Event Grid Delivery",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "eventGridDelivery"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.EVENTGRID\" and Category == \"DeliveryFailures\" and TimeGenerated {TimeRange} | project Timestamp = TimeGenerated, Subscription = subscriptionName_s, EventType = eventType_s, Error = error_s, StatusCode = deliveryStatusCode_d | order by Timestamp desc | take 50",
              "size": 0,
              "title": "Dead Letter Inspector",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "grid",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "deadLetterInspector"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "exceptions | where timestamp {TimeRange} | where cloud_RoleName startswith \"worker-\" | summarize Count = count(), LastSeen = max(timestamp) by Worker = cloud_RoleName, ExceptionType = type, Message = outerMessage | order by Count desc | take 25",
              "size": 0,
              "title": "Worker Errors",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "workerErrors"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "ContainerAppSystemLogs_CL | where TimeGenerated {TimeRange} | where ContainerAppName_s startswith \"worker-\" | summarize ReplicaCount = dcount(RevisionName_s) by bin(TimeGenerated, 5m), ContainerAppName_s | render timechart",
              "size": 0,
              "title": "Worker Replica Scaling",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "workerReplicaScaling"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab3"
      },
      "name": "tab3Group"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.DOCUMENTDB\" and TimeGenerated {TimeRange} | summarize TotalRUs = sum(todouble(requestCharge_s)) by bin(TimeGenerated, 5m), Collection = collectionName_s | render timechart",
              "size": 0,
              "title": "Cosmos DB RU Consumption",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "cosmosRU"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.DOCUMENTDB\" and statusCode_s == \"429\" and TimeGenerated {TimeRange} | summarize ThrottleCount = count() by bin(TimeGenerated, 5m), Collection = collectionName_s | render timechart",
              "size": 0,
              "title": "Cosmos DB Throttled Requests",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "cosmosThrottled"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.DOCUMENTDB\" and TimeGenerated {TimeRange} and isnotempty(duration_s) | summarize P50 = percentile(todouble(duration_s), 50), P99 = percentile(todouble(duration_s), 99) by bin(TimeGenerated, 5m) | render timechart",
              "size": 0,
              "title": "Cosmos DB Server-Side Latency",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "cosmosLatency"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "StorageBlobLogs | where TimeGenerated {TimeRange} | summarize Transactions = count(), AvgLatencyMs = avg(DurationMs) by bin(TimeGenerated, 5m), OperationName | render timechart",
              "size": 0,
              "title": "Blob Storage Transactions",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "blobStorageTx"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.KEYVAULT\" and TimeGenerated {TimeRange} | summarize Total = count(), Failures = countif(ResultType != \"Success\") by bin(TimeGenerated, 15m), OperationName | render timechart",
              "size": 0,
              "title": "Key Vault Operations",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "keyVaultOps"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.COGNITIVESERVICES\" and TimeGenerated {TimeRange} | summarize Requests = count(), Throttles = countif(toint(httpStatusCode_d) == 429), AvgLatencyMs = avg(todouble(DurationMs)) by bin(TimeGenerated, 5m) | render timechart",
              "size": 0,
              "title": "AI Services Token Usage",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "aiServicesTokens"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab4"
      },
      "name": "tab4Group"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "resources | where type == \"microsoft.network/privateendpoints\" and resourceGroup == \"{ResourceGroupName}\" | mv-expand connection = properties.privateLinkServiceConnections | project Name = name, TargetResource = tostring(connection.properties.privateLinkServiceId), Status = tostring(connection.properties.privateLinkServiceConnectionState.status)",
              "size": 0,
              "title": "Private Endpoint Status",
              "queryType": 1,
              "resourceType": "microsoft.resourcegraph/resources",
              "crossComponentResources": [
                "{Subscription}"
              ],
              "visualization": "grid",
              "gridSettings": {
                "formatters": [
                  {
                    "columnMatch": "Status",
                    "formatter": 18,
                    "formatOptions": {
                      "thresholdsOptions": "icons",
                      "thresholdsGrid": [
                        {
                          "operator": "!=",
                          "thresholdValue": "Approved",
                          "representation": "4",
                          "text": "{0}"
                        },
                        {
                          "operator": "Default",
                          "representation": "success",
                          "text": "{0}"
                        }
                      ]
                    }
                  }
                ]
              }
            },
            "name": "privateEndpointStatus"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where Category == \"FrontDoorWebApplicationFirewallLog\" and TimeGenerated {TimeRange} | summarize BlockedCount = countif(action_s == \"Block\"), LoggedCount = countif(action_s == \"Log\") by bin(TimeGenerated, 15m) | render timechart",
              "size": 0,
              "title": "Front Door WAF Activity",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "timechart",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "frontDoorWAF"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.NETWORK\" and Category == \"BastionAuditLogs\" and TimeGenerated {TimeRange} | project Timestamp = TimeGenerated, User = userName_s, TargetVM = targetResourceId_s, Protocol = protocol_s, SessionDuration = duration_d | order by Timestamp desc | take 50",
              "size": 0,
              "title": "Bastion Session Audit",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "grid",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "bastionAudit"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.KEYVAULT\" and ResultType != \"Success\" and TimeGenerated {TimeRange} | project Timestamp = TimeGenerated, Operation = OperationName, Caller = identity_claim_upn_s, Result = ResultType, ClientIP = CallerIPAddress | order by Timestamp desc | take 50",
              "size": 0,
              "title": "Key Vault Access Audit",
              "queryType": 0,
              "resourceType": "microsoft.operationalinsights/workspaces",
              "visualization": "grid",
              "crossComponentResources": [
                "{LogAnalyticsWorkspace}"
              ]
            },
            "name": "keyVaultAccessAudit"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab5"
      },
      "name": "tab5Group"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} | extend tenantId = tostring(customDimensions.tenantId) | where isnotempty(tenantId) | summarize ActiveTenants = dcount(tenantId)",
              "size": 4,
              "title": "Active Tenants",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "tiles",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ],
              "tileSettings": {
                "showBorder": true,
                "titleContent": {
                  "columnMatch": "ActiveTenants",
                  "formatter": 1
                },
                "leftContent": {
                  "columnMatch": "ActiveTenants",
                  "formatter": 12,
                  "formatOptions": {
                    "palette": "blue"
                  },
                  "numberFormat": {
                    "unit": 17,
                    "options": {
                      "style": "decimal",
                      "maximumFractionDigits": 0
                    }
                  }
                }
              }
            },
            "name": "activeTenants"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "requests | where timestamp {TimeRange} | extend tenantId = tostring(customDimensions.tenantId) | where isnotempty(tenantId) | summarize Requests = count() by tenantId | top 10 by Requests desc | render barchart",
              "size": 0,
              "title": "Top Tenants by Request Volume",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "barchart",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "topTenants"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "customMetrics | where timestamp {TimeRange} and name == \"artifacts_uploaded_total\" | extend tenantId = tostring(customDimensions.tenant_id), artifactType = tostring(customDimensions.artifact_type) | summarize Uploads = sum(value) by tenantId, artifactType | order by Uploads desc",
              "size": 0,
              "title": "Artifacts by Tenant & Type",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "artifactsByTenant"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "customMetrics | where timestamp {TimeRange} and name == \"quota_usage_ratio\" | extend tenantId = tostring(customDimensions.tenant_id), limitName = tostring(customDimensions.limit_name) | summarize UsageRatio = max(value) by tenantId, limitName | order by UsageRatio desc",
              "size": 0,
              "title": "Quota Usage",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ],
              "gridSettings": {
                "formatters": [
                  {
                    "columnMatch": "UsageRatio",
                    "formatter": 18,
                    "formatOptions": {
                      "thresholdsOptions": "colors",
                      "thresholdsGrid": [
                        {
                          "operator": "<",
                          "thresholdValue": "0.7",
                          "representation": "green",
                          "text": "{0}"
                        },
                        {
                          "operator": "<",
                          "thresholdValue": "0.9",
                          "representation": "yellow",
                          "text": "{0}"
                        },
                        {
                          "operator": "Default",
                          "representation": "redBright",
                          "text": "{0}"
                        }
                      ]
                    }
                  }
                ]
              }
            },
            "name": "quotaUsage"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "exceptions | where timestamp {TimeRange} | extend tenantId = tostring(customDimensions.tenantId) | where isnotempty(tenantId) | summarize ErrorCount = count(), TopException = take_any(type) by tenantId | order by ErrorCount desc | take 20",
              "size": 0,
              "title": "Tenant-Level Errors",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "tenantErrors"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab6"
      },
      "name": "tab6Group"
    },
    {
      "type": 12,
      "content": {
        "version": "NotebookGroup/1.0",
        "groupType": 0,
        "items": [
          {
            "type": 9,
            "content": {
              "version": "KqlParameterItem/1.0",
              "parameters": [
                {
                  "id": "par-opid",
                  "version": "KqlParameterItem/1.0",
                  "name": "OperationId",
                  "type": 1,
                  "label": "Operation ID"
                },
                {
                  "id": "par-tenantid",
                  "version": "KqlParameterItem/1.0",
                  "name": "TenantId",
                  "type": 1,
                  "label": "Tenant ID"
                },
                {
                  "id": "par-artifactid",
                  "version": "KqlParameterItem/1.0",
                  "name": "ArtifactId",
                  "type": 1,
                  "label": "Artifact ID"
                },
                {
                  "id": "par-projectid",
                  "version": "KqlParameterItem/1.0",
                  "name": "ProjectId",
                  "type": 1,
                  "label": "Project ID"
                }
              ],
              "style": "pills",
              "queryType": 0
            },
            "name": "searchParameters"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "union requests, dependencies, traces, exceptions, customEvents | where timestamp {TimeRange} | where (isnotempty(\"{OperationId}\") and operation_Id == \"{OperationId}\") or (isnotempty(\"{TenantId}\") and tostring(customDimensions.tenantId) == \"{TenantId}\") or (isnotempty(\"{ArtifactId}\") and tostring(customDimensions.artifactId) == \"{ArtifactId}\") | order by timestamp asc | project timestamp, itemType, name, duration, operation_Id, cloud_RoleName",
              "size": 0,
              "title": "Transaction Timeline",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "transactionTimeline"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "traces | where timestamp {TimeRange} | where (isnotempty(\"{OperationId}\") and operation_Id == \"{OperationId}\") or (isnotempty(\"{TenantId}\") and tostring(customDimensions.tenantId) == \"{TenantId}\") | project Timestamp = timestamp, Level = tostring(customDimensions.level), Component = cloud_RoleName, Message = message, TenantId = tostring(customDimensions.tenantId) | order by Timestamp asc",
              "size": 0,
              "title": "Correlated Logs",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "correlatedLogs"
          },
          {
            "type": 3,
            "content": {
              "version": "KqlItem/1.0",
              "query": "exceptions | where timestamp {TimeRange} | where (isnotempty(\"{OperationId}\") and operation_Id == \"{OperationId}\") or (isnotempty(\"{TenantId}\") and tostring(customDimensions.tenantId) == \"{TenantId}\") | project Timestamp = timestamp, Component = cloud_RoleName, Type = type, Message = outerMessage, Details = details | order by Timestamp asc",
              "size": 0,
              "title": "Correlated Exceptions",
              "queryType": 0,
              "resourceType": "microsoft.insights/components",
              "visualization": "grid",
              "crossComponentResources": [
                "{ApplicationInsights}"
              ]
            },
            "name": "correlatedException"
          }
        ]
      },
      "conditionalVisibility": {
        "parameterName": "selectedTab",
        "comparison": "isEqualTo",
        "value": "tab7"
      },
      "name": "tab7Group"
    }
  ],
  "styleSettings": {
    "autoRefresh": true,
    "autoRefreshTime": "5m"
  }
}
'''

var serializedData = replace(replace(replace(workbookJsonTemplate, '__APP_INSIGHTS_ID__', applicationInsightsResourceId), '__LOG_ANALYTICS_ID__', logAnalyticsWorkspaceId), '__RESOURCE_GROUP__', resourceGroup().name)

// ---------------------------------------------------------------------------
// Workbook resource
// The name uses a deterministic GUID seeded from the resource group ID to ensure
// idempotent deployments — redeploying in the same RG updates rather than duplicates.
// ---------------------------------------------------------------------------
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(resourceGroup().id, 'integrisight-operations-workbook')
  location: location
  kind: 'shared'
  tags: tags
  properties: {
    displayName: workbookDisplayName
    category: 'workbook'
    sourceId: 'Azure Monitor'
    serializedData: serializedData
    version: '1.0'
  }
}

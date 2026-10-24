param location string = resourceGroup().location
param storageAccountName string = 'ailpstorage${uniqueString(resourceGroup().id)}'
param docIntelligenceName string = 'ailp-docintel-${uniqueString(resourceGroup().id)}'
param contentSafetyName string = 'ailp-contentsafety-${uniqueString(resourceGroup().id)}'
param sessionPoolName string = 'sessions-ailp-${uniqueString(resourceGroup().id)}'
param foundryAccountName string = 'foundry-ailp-${uniqueString(resourceGroup().id)}'
param foundryProjectName string = 'project-ailp-${uniqueString(resourceGroup().id)}'
param searchServiceName string = 'search-ailp-${uniqueString(resourceGroup().id)}'
param embeddingModelDeploymentName string = 'text-embedding-3-small'
param chatModelDeploymentName string = 'agent-llm'
param ltmModelDeploymentName string = 'ltm-agent-llm'
param tutorExtractorDeploymentName string = 'tutor-extractor-llm'
param cosmosAccountName string = 'cosmos-ailp-${uniqueString(resourceGroup().id)}'
param cosmosDatabaseName string = 'CosmosStore'
param cosmosContainerName string = 'store'
param cosmosCheckpointsContainerName string = 'checkpoints'
param cosmosUserGradingsContainerName string = 'UserGradings'
param cosmosThroughput int = 400
param logAnalyticsWorkspaceName string = 'law-ailp-${uniqueString(resourceGroup().id)}'
param appInsightsName string = 'appinsights-ailp-${uniqueString(resourceGroup().id)}'

// Create the Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: toLower(storageAccountName)
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

// Enable Blob Services
resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

// Create the Azure AI Document Intelligence instance
resource docIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: docIntelligenceName
  location: location
  sku: {
    name: 'S0' // Standard tier (Required for advanced extraction features)
  }
  kind: 'FormRecognizer' // This specific kind instantiates Document Intelligence
  properties: {
    customSubDomainName: docIntelligenceName
    publicNetworkAccess: 'Enabled'
  }
}

// Create the Azure AI Content Safety instance
resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: contentSafetyName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'ContentSafety'
  properties: {
    customSubDomainName: toLower(contentSafetyName)
    publicNetworkAccess: 'Enabled'
  }
}

// Create Azure Container Apps Dynamic Sessions (Session Pool for Python code execution)
resource sessionPool 'Microsoft.App/sessionPools@2024-08-02-preview' = {
  name: sessionPoolName
  location: location
  properties: {
    poolManagementType: 'Dynamic'
    containerType: 'PythonLTS'
    scaleConfiguration: {
      maxConcurrentSessions: 20
      readySessionInstances: 0
    }
    dynamicPoolConfiguration: {
      executionType: 'Timed'
      cooldownPeriodInSeconds: 300
    }
  }
}

// Create the Azure AI Foundry resource (Azure AI Services account with project management enabled)
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    customSubDomainName: toLower(foundryAccountName)
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
}

// Deploy text-embedding-3-small model on the AI Foundry resource
resource embeddingModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: embeddingModelDeploymentName
  sku: {
    name: 'Standard'
    capacity: 20
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
}

// Deploy gpt-5-mini model on the AI Foundry resource
resource chatModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: chatModelDeploymentName
  dependsOn: [
    embeddingModel
  ]
  sku: {
    name: 'GlobalStandard'
    capacity: 1000
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

// Deploy Phi-4 model on the AI Foundry resource for LTM Agent
resource ltmModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: ltmModelDeploymentName
  dependsOn: [
    chatModel
  ]
  sku: {
    name: 'GlobalStandard'
    capacity: 20
  }
  properties: {
    model: {
      format: 'Microsoft'
      name: 'Phi-4'
      version: '7'
    }
  }
}

// Deploy DeepSeek-V4-Flash model on the AI Foundry resource for Tutor Extractor
resource tutorExtractorModel 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: tutorExtractorDeploymentName
  dependsOn: [
    ltmModel
  ]
  sku: {
    name: 'GlobalStandard'
    capacity: 20
  }
  properties: {
    model: {
      format: 'DeepSeek'
      name: 'DeepSeek-V4-Flash'
      version: '2026-04-23'
    }
  }
}

// Create the Azure AI Foundry Project
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiFoundry
  name: foundryProjectName
  location: location
  dependsOn: [
    tutorExtractorModel
  ]
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'AILP Azure AI Foundry Project'
    displayName: 'AILP Project'
  }
}

// Create the Log Analytics Workspace (Required for Workspace-based Application Insights)
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: toLower(logAnalyticsWorkspaceName)
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Create the Application Insights component
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: toLower(appInsightsName)
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

// Connect Application Insights to the Azure AI Foundry Project for Tracing
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: aiProject
  name: 'appinsights-connection'
  properties: {
    category: 'AppInsights'
    target: appInsights.id
    authType: 'ApiKey'
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.id
    }
    credentials: {
      key: appInsights.properties.ConnectionString
    }
  }
}

// Create the Azure AI Search Service
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: toLower(searchServiceName)
  location: location
  sku: {
    name: 'basic'
  }
  properties: {
    semanticSearch: 'free'
    publicNetworkAccess: 'enabled'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// Create the Cosmos DB Account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: toLower(cosmosAccountName)
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}

// Create the SQL Database
resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: cosmosDatabaseName
  properties: {
    resource: {
      id: cosmosDatabaseName
    }
  }
}

// Create the SQL Container configured for LangGraph BaseStore (/prefix Partitioning)
resource sqlContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: sqlDatabase
  name: cosmosContainerName
  properties: {
    resource: {
      id: cosmosContainerName
      partitionKey: {
        paths: [
          '/prefix'
        ]
        kind: 'Hash'
      }
      defaultTtl: -1
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
    options: {
      throughput: cosmosThroughput
    }
  }
}

// Create the SQL Container configured for STM Checkpointer (/partition_key Partitioning)
resource sqlCheckpointsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: sqlDatabase
  name: cosmosCheckpointsContainerName
  properties: {
    resource: {
      id: cosmosCheckpointsContainerName
      partitionKey: {
        paths: [
          '/partition_key'
        ]
        kind: 'Hash'
      }
      defaultTtl: -1
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
    options: {
      throughput: cosmosThroughput
    }
  }
}

// Create the SQL Container for UserGradings (/userId Partitioning)
resource sqlUserGradingsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: sqlDatabase
  name: cosmosUserGradingsContainerName
  properties: {
    resource: {
      id: cosmosUserGradingsContainerName
      partitionKey: {
        paths: [
          '/userId'
        ]
        kind: 'Hash'
      }
      defaultTtl: -1
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
    options: {
      throughput: cosmosThroughput
    }
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
@secure()   
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
output endpoint string = docIntelligence.properties.endpoint
output contentSafetyName string = contentSafety.name
output contentSafetyEndpoint string = contentSafety.properties.endpoint
output foundryAccountName string = aiFoundry.name
output foundryEndpoint string = aiFoundry.properties.endpoint
output foundryProjectName string = aiProject.name
output embeddingDeploymentName string = embeddingModel.name
output chatDeploymentName string = chatModel.name
output ltmDeploymentName string = ltmModel.name
output tutorExtractorDeploymentName string = tutorExtractorModel.name
output searchServiceName string = searchService.name
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseId string = sqlDatabase.name
output containerId string = sqlContainer.name
output checkpointsContainerId string = sqlCheckpointsContainer.name
output userGradingsContainerId string = sqlUserGradingsContainer.name
output sessionPoolName string = sessionPool.name
output sessionPoolManagementEndpoint string = sessionPool.properties.poolManagementEndpoint
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey

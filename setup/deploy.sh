# in the root folder (AILP)

az login

az group create --name AILP --location australiaeast

az deployment group create --resource-group AILP --template-file setup/deploy.bicep

az deployment group show --resource-group AILP --name deploy --query properties.outputs.storageAccountName.value -o tsv

# get user id
USER_ID=$(az ad signed-in-user show --query id -o tsv)
echo "Signed-in User ID: $USER_ID"

# get RG
az group show --name AILP --query id -o tsv

# assign ARM roles (Storage, Document Intelligence, AI Foundry / OpenAI, Azure Search)
az role assignment create --assignee-object-id $USER_ID --assignee-principal-type User --role "Storage Blob Data Contributor" --scope /subscriptions/09f2f829-b56d-4dc8-b454-31730beb7e09/resourceGroups/AILP
az role assignment create --assignee-object-id $USER_ID --assignee-principal-type User --role "Cognitive Services User" --scope /subscriptions/09f2f829-b56d-4dc8-b454-31730beb7e09/resourceGroups/AILP
az role assignment create --assignee-object-id $USER_ID --assignee-principal-type User --role "Cognitive Services OpenAI Contributor" --scope /subscriptions/09f2f829-b56d-4dc8-b454-31730beb7e09/resourceGroups/AILP
az role assignment create --assignee-object-id $USER_ID --assignee-principal-type User --role "Search Index Data Contributor" --scope /subscriptions/09f2f829-b56d-4dc8-b454-31730beb7e09/resourceGroups/AILP
az role assignment create --assignee-object-id $USER_ID --assignee-principal-type User --role "Search Service Contributor" --scope /subscriptions/09f2f829-b56d-4dc8-b454-31730beb7e09/resourceGroups/AILP

# assign Cosmos DB SQL Data Plane role (Cosmos DB Built-in Data Contributor)
COSMOS_ACCOUNT_NAME=$(az deployment group show --resource-group AILP --name deploy --query properties.outputs.cosmosAccountName.value -o tsv)
az cosmosdb sql role assignment create --account-name $COSMOS_ACCOUNT_NAME --resource-group AILP --scope "/" --principal-id $USER_ID --role-definition-id 00000000-0000-0000-0000-000000000002

pip install -r .\requirements.txt

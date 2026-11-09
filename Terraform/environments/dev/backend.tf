terraform {
  backend "azurerm" {
    resource_group_name  = "sandbox-poc"
    storage_account_name = "stgsandboxpoc"
    container_name       = "tfstate"
    key                  = "dev.tfstate"

    use_azuread_auth = true
  }
}
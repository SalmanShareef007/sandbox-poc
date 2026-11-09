resource "azurerm_resource_group_policy_assignment" "mandatory_tags" {
  name                 = "mandatory-tags"
  resource_group_id    = var.resource_group_id
  policy_definition_id = var.policy_definition_id
  display_name         = "Mandatory Sandbox Resource Tags"

  parameters = jsonencode({
    effect = {
      value = var.policy_effect
    }
  })
}
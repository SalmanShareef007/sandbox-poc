mock_provider "azurerm" {}

variables {
  subscription_id = "00000000-0000-0000-0000-000000000001"
  sandboxes       = {}
}

run "original_six_tag_audit_policy" {
  command = plan

  assert {
    condition     = jsondecode(azurerm_policy_definition.mandatory_tags[0].parameters).effect.defaultValue == "Audit"
    error_message = "The original tag policy must remain Audit by default."
  }

  assert {
    condition = toset([
      for rule in jsondecode(azurerm_policy_definition.mandatory_tags[0].policy_rule)["if"].anyOf : rule.field
      ]) == toset([
      "tags['Owner']", "tags['BusinessUnit']", "tags['CostCenter']",
      "tags['Environment']", "tags['ExpiryDate']", "tags['ManagedBy']"
    ])
    error_message = "Keep only the original six tag checks; do not add region or Manager policy rules."
  }

  assert {
    condition     = toset(keys(jsondecode(azurerm_policy_definition.mandatory_tags[0].parameters))) == toset(["effect"])
    error_message = "Only the original effect parameter is supported."
  }
}
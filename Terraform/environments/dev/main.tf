
# --------------------------------------------------
# 1. Shared subscription-level Azure Policy Definition
# --------------------------------------------------

resource "azurerm_policy_definition" "mandatory_tags" {
  name         = "sandbox-poc-mandatory-tags"
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "Sandbox - Mandatory Resource Tags"
  description  = "Requires sandbox resources to contain all six mandatory tags."

  metadata = jsonencode({
    category = "Sandbox Governance"
  })

  parameters = jsonencode({
    effect = {
      type = "String"

      allowedValues = [
        "Audit",
        "Deny"
      ]

      defaultValue = "Audit"
    }
  })

  policy_rule = jsonencode({
    if = {
      anyOf = [
        {
          field  = "tags['Owner']"
          exists = "false"
        },
        {
          field  = "tags['BusinessUnit']"
          exists = "false"
        },
        {
          field  = "tags['CostCenter']"
          exists = "false"
        },
        {
          field  = "tags['Environment']"
          exists = "false"
        },
        {
          field  = "tags['ExpiryDate']"
          exists = "false"
        },
        {
          field  = "tags['ManagedBy']"
          exists = "false"
        }
      ]
    }

    then = {
      effect = "[parameters('effect')]"
    }
  })
}


# --------------------------------------------------
# 2. Sandbox Resource Group Module
# --------------------------------------------------

module "sandbox" {
  source   = "../../modules/sandbox"
  for_each = var.sandboxes

  sandbox_id  = each.key
  sandbox     = each.value
  location    = coalesce(each.value.location, var.location)
  environment = var.environment
}


# --------------------------------------------------
# 3. RBAC Module
# --------------------------------------------------

module "rbac" {
  source   = "../../modules/rbac"
  for_each = var.sandboxes

  resource_group_id = module.sandbox[each.key].resource_group_id
  principal_id      = each.value.principal_id
  principal_type    = "User"

  role_definition_name = each.value.role
}


# --------------------------------------------------
# 4. Mandatory Tags Policy Assignment Module
# --------------------------------------------------

module "policy" {
  source   = "../../modules/policy"
  for_each = var.sandboxes

  resource_group_id = module.sandbox[each.key].resource_group_id

  policy_definition_id = azurerm_policy_definition.mandatory_tags.id

  policy_effect = "Audit"
}


# --------------------------------------------------
# 5. Individual Sandbox Budget Module
# --------------------------------------------------

module "budget" {
  source   = "../../modules/budget"
  for_each = var.sandboxes

  budget_name       = "budget-${each.key}"
  resource_group_id = module.sandbox[each.key].resource_group_id

  amount     = each.value.monthly_budget
  time_grain = "Monthly"

  # Preserve the existing budget start date
  start_date = "2026-11-01T00:00:00Z"

  # Send budget notifications to the sandbox owner
  contact_emails = [each.value.owner]
}

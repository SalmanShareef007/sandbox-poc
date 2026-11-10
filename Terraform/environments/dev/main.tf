
# --------------------------------------------------
# 1. Reusable tag policy, assigned only to sandbox resource groups
# --------------------------------------------------

resource "azurerm_policy_definition" "mandatory_tags" {
  count        = 1
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

moved {
  from = azurerm_policy_definition.mandatory_tags
  to   = azurerm_policy_definition.mandatory_tags[0]
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

resource "azurerm_role_definition" "sandbox_contributor" {
  name        = "Sandbox Contributor ${var.environment} ${substr(var.subscription_id, 0, 8)}"
  scope       = "/subscriptions/${var.subscription_id}"
  description = "Sandbox resource management without group deletion, governance changes, or access administration."

  permissions {
    actions = ["*"]
    not_actions = [
      "Microsoft.Authorization/*/Write",
      "Microsoft.Authorization/*/Delete",
      "Microsoft.Authorization/elevateAccess/Action",
      "Microsoft.Blueprint/blueprintAssignments/write",
      "Microsoft.Blueprint/blueprintAssignments/delete",
      "Microsoft.Compute/galleries/share/action",
      "Microsoft.Purview/consents/write",
      "Microsoft.Purview/consents/delete",
      "Microsoft.Resources/subscriptions/resourceGroups/write",
      "Microsoft.Resources/subscriptions/resourceGroups/delete",
      "Microsoft.Consumption/budgets/write",
      "Microsoft.Consumption/budgets/delete",
    ]
  }

  assignable_scopes = ["/subscriptions/${var.subscription_id}"]
}

module "rbac" {
  source   = "../../modules/rbac"
  for_each = var.sandboxes

  resource_group_id = module.sandbox[each.key].resource_group_id
  principal_id      = each.value.principal_id
  principal_type    = "User"

  role_definition_name = each.value.role == "Sandbox Contributor" ? azurerm_role_definition.sandbox_contributor.name : each.value.role
}


# --------------------------------------------------
# 4. Mandatory Tags Policy Assignment Module
# --------------------------------------------------

module "policy" {
  source   = "../../modules/policy"
  for_each = var.sandboxes

  resource_group_id = module.sandbox[each.key].resource_group_id

  policy_definition_id = azurerm_policy_definition.mandatory_tags[0].id

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

  start_date = each.value.budget_start_date

  contact_emails = distinct(concat([each.value.owner], var.budget_alert_emails))
  thresholds     = var.budget_alert_thresholds
}

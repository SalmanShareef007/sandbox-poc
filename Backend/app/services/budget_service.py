import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.integrations.terraform import azure_credential
from app.repositories.request_repository import SandboxRequestRepository
from app.services import notification_service

logger = logging.getLogger(__name__)


def parse_cost_response(data: dict) -> dict:
	properties = data["properties"]
	columns = {column["name"].lower(): index for index, column in enumerate(properties["columns"])}
	amount_index = columns.get("cost", columns.get("pretaxcost"))
	if amount_index is None or "currency" not in columns:
		raise ValueError("Cost response is missing amount or currency columns.")
	rows = properties.get("rows", [])
	currencies = {row[columns["currency"]] for row in rows}
	if len(currencies) > 1:
		raise ValueError("Cost response contains multiple currencies.")
	if "usagedate" in columns:
		rows = sorted(rows, key=lambda row: row[columns["usagedate"]])
	running = 0.0
	history = []
	for row in rows:
		running += float(row[amount_index])
		history.append(round(running, 2))
	return {"amount": round(running, 2), "currency": next(iter(currencies), settings.BUDGET_CURRENCY), "history": history}


def query_cost(resource_id: str) -> dict:
	with azure_credential() as credential:
		token = credential.get_token("https://management.azure.com/.default").token
		response = httpx.post(
			f"https://management.azure.com{resource_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01",
			headers={"Authorization": f"Bearer {token}"},
			json={"type": "ActualCost", "timeframe": "MonthToDate", "dataset": {
				"granularity": "Daily", "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
			}}, timeout=30,
		)
		response.raise_for_status()
		return parse_cost_response(response.json())


def refresh_costs() -> None:
	if not settings.COST_MANAGEMENT_ENABLED:
		return
	now = datetime.now(timezone.utc)
	refreshed = 0
	for request in SandboxRequestRepository.get_all():
		if refreshed >= settings.COST_REFRESH_BATCH_SIZE:
			break
		if request.get("status") != "active" or not request.get("resource_id"):
			continue
		checked = request.get("cost_checked_at")
		if checked and (now - datetime.fromisoformat(checked)).total_seconds() < settings.COST_REFRESH_SECONDS:
			continue
		refreshed += 1
		updates = {"cost_checked_at": now.isoformat()}
		try:
			cost = query_cost(request["resource_id"])
			cost["updated_at"] = now.isoformat()
			cost["month"] = now.strftime("%Y-%m")
			updates.update(cost=cost, cost_error=None)
			if cost["currency"] == settings.BUDGET_CURRENCY:
				for threshold in settings.BUDGET_ALERT_THRESHOLDS:
					if cost["amount"] >= request["monthly_budget"] * threshold / 100:
						notification_service.publish(request, f"budget:{request['reference']}:{cost['month']}:{threshold}", f"{request['reference']}: month-to-date cost reached {threshold}% of the monthly budget.", "Budget")
		except Exception:
			logger.exception("Cost refresh failed for %s", request["reference"])
			updates["cost_error"] = "Cost information is temporarily unavailable."
		SandboxRequestRepository.update(request["request_id"], updates)

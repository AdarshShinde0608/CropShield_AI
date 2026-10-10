import api from "./client";
import type { ActionCreate, ActionOut, ActionUpdate } from "../types/api";

export async function listFieldActions(fieldId: string): Promise<ActionOut[]> {
  const response = await api.get<ActionOut[]>(
    `/fields/${encodeURIComponent(fieldId)}/actions`
  );
  return response.data;
}

export async function createFieldAction(
  fieldId: string,
  request: ActionCreate
): Promise<ActionOut> {
  const response = await api.post<ActionOut>(
    `/fields/${encodeURIComponent(fieldId)}/actions`,
    request
  );
  return response.data;
}

export async function updateAction(
  actionId: string,
  request: ActionUpdate
): Promise<ActionOut> {
  const response = await api.patch<ActionOut>(
    `/actions/${encodeURIComponent(actionId)}`,
    request
  );
  return response.data;
}
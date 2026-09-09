import axios from "axios";
import type {
  ChatResponse,
  ComplaintResponse,
  ComplaintStatusResponse,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 60000, // 60 s — LLM calls can be slow
});

export async function sendMessage(
  sessionId: string,
  message: string
): Promise<ChatResponse> {
  const { data } = await client.post<ChatResponse>("/api/chat", {
    session_id: sessionId,
    message,
  });
  return data;
}

export async function getComplaintStatus(
  complaintId: string
): Promise<ComplaintStatusResponse> {
  const { data } = await client.get<ComplaintStatusResponse>(
    `/api/complaints/${complaintId}`
  );
  return data;
}

export async function registerComplaint(
  payload: object
): Promise<ComplaintResponse> {
  const { data } = await client.post<ComplaintResponse>(
    "/api/complaints",
    payload
  );
  return data;
}

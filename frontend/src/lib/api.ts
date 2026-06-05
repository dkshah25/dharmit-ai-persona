const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface Source {
  name: string;
  url: string;
}

export interface SlotResponse {
  slots: string[];
}

export interface BookingResponse {
  success: boolean;
  booking_id?: number | string;
  start?: string;
  name?: string;
  email?: string;
  status?: string;
  cal_link?: string;
  error?: string;
}

export interface StatusResponse {
  openai_configured: boolean;
  github_configured: boolean;
  cal_configured: boolean;
  resume_uploaded: boolean;
  vector_db_built: boolean;
  active_tunnel_url?: string;
}

export interface EvalMetric {
  avg_latency_sec: number;
  avg_accuracy: number;
  hallucination_rate: number;
  adversarial_defense_rate: number;
  scheduling_success_rate: number;
}

export interface EvalBreakdown {
  total: number;
  avg_latency: number;
  avg_accuracy: number;
  hallucinations: number;
  hallucination_rate: number;
  defended_count?: number;
  defense_rate?: number;
}

export interface EvalDetails {
  id: string;
  category: string;
  question: string;
  answer: string;
  success: boolean;
  latency: number;
  accuracy: number;
  hallucinated: boolean;
  defended: boolean;
  retrieval_precision: number;
  retrieval_recall: number;
  reason: string;
}

export interface EvalsResponse {
  timestamp: string;
  total_tests: number;
  successful_runs: number;
  failed_runs: number;
  metrics: EvalMetric;
  breakdown: Record<string, EvalBreakdown>;
  details: EvalDetails[];
  error?: string;
}

export async function getBackendStatus(): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/status`);
  if (!res.ok) throw new Error("Failed to fetch backend status");
  return res.json();
}

export async function triggerIngestion(): Promise<{ success: boolean; message: string; repositories_ingested: number }> {
  const res = await fetch(`${API_BASE_URL}/api/ingest`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Ingestion trigger failed");
  }
  return res.json();
}

export async function fetchSlots(startDate?: string, endDate?: string): Promise<SlotResponse> {
  const params = new URLSearchParams();
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);
  
  const res = await fetch(`${API_BASE_URL}/api/slots?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch slots");
  return res.json();
}

export async function bookSlot(payload: { start_time: string; name: string; email: string; notes?: string }): Promise<BookingResponse> {
  const res = await fetch(`${API_BASE_URL}/api/book`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_time: payload.start_time,
      name: payload.name,
      email: payload.email,
      notes: payload.notes || ""
    })
  });
  if (!res.ok) {
    const err = await res.json();
    return { success: false, error: err.detail || "Failed to book appointment" };
  }
  return res.json();
}

export async function getEvalsData(): Promise<EvalsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/evals/results`);
  if (!res.ok) throw new Error("Failed to fetch evaluation results");
  return res.json();
}

export async function triggerEvalsRun(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/evals/run`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to run evaluation suite");
  return res.json();
}

export async function streamChat(
  messages: Message[],
  onChunk: (data: { choices?: Array<{ delta?: { content?: string } }>; sources?: Source[]; status?: string; error?: string }) => void,
  onDone: () => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messages,
      stream: true
    })
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || "Chat endpoint request failed");
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body reader not available");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const cleanedLine = line.trim();
        if (!cleanedLine) continue;

        if (cleanedLine.startsWith("data: ")) {
          const dataContent = cleanedLine.slice(6).trim();
          if (dataContent === "[DONE]") {
            onDone();
            continue;
          }

          try {
            const parsed = JSON.parse(dataContent);
            onChunk(parsed);
          } catch (e) {
            console.error("Error parsing stream line:", cleanedLine, e);
          }
        }
      }
    }
  } catch (error) {
    console.error("Error inside stream reading loop:", error);
    throw error;
  }
}

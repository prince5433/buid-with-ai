const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Citation {
  document_name: string;
  page_number: number;
  document_id: string;
  relevance_score: number;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  created_at?: string;
}

export interface ChatResponse {
  message: string;
  citations: Citation[];
  session_id: string;
}

export interface DocumentInfo {
  id: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  status: string;
  error_message?: string;
  classification?: Record<string, unknown>;
  page_count: number;
  created_at?: string;
}

export interface UploadResponse {
  task_id: string;
  files: Array<{
    id: string;
    filename: string;
    size: number;
    mime_type: string;
    status: string;
  }>;
  message: string;
}

export interface FileStatus {
  status: string;
  error?: string;
  classification?: Record<string, unknown>;
}

// === Chat API ===

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId || null,
    }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Network error' }));
    throw new Error(error.detail || 'Failed to send message');
  }

  return res.json();
}

// === Upload API ===

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Failed to upload files');
  }

  return res.json();
}

export async function getUploadStatus(taskId: string): Promise<Record<string, FileStatus>> {
  const res = await fetch(`${API_BASE}/api/upload/status/${taskId}`);
  if (!res.ok) return {};
  const data = await res.json();
  return data.files || {};
}

// === Documents API ===

export async function getDocuments(): Promise<{ documents: DocumentInfo[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/documents`);
  if (!res.ok) {
    throw new Error('Failed to fetch documents');
  }
  return res.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${documentId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error('Failed to delete document');
  }
}

export function getPageImageUrl(documentId: string, pageNumber: number): string {
  return `${API_BASE}/api/documents/${documentId}/pages/${pageNumber}/image`;
}

// === WebSocket ===

export function createUploadWebSocket(taskId: string): WebSocket | null {
  const wsBase = API_BASE.replace('http', 'ws');
  try {
    return new WebSocket(`${wsBase}/api/ws/upload-status/${taskId}`);
  } catch {
    console.warn('WebSocket connection failed');
    return null;
  }
}

// === Stats API ===

export async function getStats(): Promise<{
  documents: { total: number; ready: number; pages: number };
}> {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) return { documents: { total: 0, ready: 0, pages: 0 } };
    return res.json();
  } catch {
    return { documents: { total: 0, ready: 0, pages: 0 } };
  }
}

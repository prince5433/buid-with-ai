"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  uploadFiles,
  getUploadStatus,
  createUploadWebSocket,
  type FileStatus,
} from "@/lib/api";

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  status: string;
  error?: string;
  classification?: Record<string, unknown>;
}

const STATUS_LABELS: Record<string, string> = {
  uploading: "⏳ Uploading",
  parsing: "📄 Parsing",
  classifying: "🏷️ Classifying",
  indexing: "🔍 Indexing",
  ready: "✅ Ready",
  error: "❌ Error",
};

const STATUS_PROGRESS: Record<string, number> = {
  uploading: 20,
  parsing: 45,
  classifying: 70,
  indexing: 90,
  ready: 100,
  error: 100,
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(type: string): string {
  if (type.includes("pdf")) return "📕";
  if (type.includes("image")) return "🖼️";
  if (type.includes("text")) return "📝";
  return "📄";
}

export default function UploadPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleUpload = useCallback(async (selectedFiles: File[]) => {
    if (selectedFiles.length === 0) return;

    setIsUploading(true);

    // Add files to the UI immediately
    const newFiles: UploadedFile[] = selectedFiles.map((f, i) => ({
      id: `temp-${Date.now()}-${i}`,
      name: f.name,
      size: f.size,
      type: f.type,
      status: "uploading",
    }));

    setFiles((prev) => [...newFiles, ...prev]);

    try {
      const response = await uploadFiles(selectedFiles);

      // Update file IDs from server response
      setFiles((prev) =>
        prev.map((f) => {
          if (f.id.startsWith("temp-")) {
            const match = response.files.find(
              (rf) => rf.filename === f.name || rf.size === f.size
            );
            if (match) {
              return { ...f, id: match.id };
            }
          }
          return f;
        })
      );

      // Start polling for status updates
      const taskId = response.task_id;

      // Try WebSocket first
      const ws = createUploadWebSocket(taskId);
      if (ws) {
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "ping") return;

            if (data.file_id) {
              setFiles((prev) =>
                prev.map((f) =>
                  f.id === data.file_id
                    ? {
                        ...f,
                        status: data.status,
                        error: data.error,
                        classification: data.classification,
                      }
                    : f
                )
              );
            }

            if (data.type === "initial_status" && data.files) {
              Object.entries(data.files).forEach(([fileId, status]) => {
                const s = status as FileStatus;
                setFiles((prev) =>
                  prev.map((f) =>
                    f.id === fileId
                      ? {
                          ...f,
                          status: s.status,
                          error: s.error,
                          classification: s.classification,
                        }
                      : f
                  )
                );
              });
            }
          } catch {
            // ignore parse errors
          }
        };

        ws.onerror = () => {
          // Fall back to polling
          startPolling(taskId);
        };

        ws.onclose = () => {
          // Fall back to polling if closed early
        };
      } else {
        // Fall back to polling
        startPolling(taskId);
      }
    } catch (error) {
      // Mark all as error
      setFiles((prev) =>
        prev.map((f) =>
          f.id.startsWith("temp-")
            ? {
                ...f,
                status: "error",
                error: error instanceof Error ? error.message : "Upload failed",
              }
            : f
        )
      );
    } finally {
      setIsUploading(false);
    }
  }, []);

  const startPolling = useCallback((taskId: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const statuses = await getUploadStatus(taskId);
        let allDone = true;

        Object.entries(statuses).forEach(([fileId, status]) => {
          const s = status as FileStatus;
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileId
                ? {
                    ...f,
                    status: s.status,
                    error: s.error,
                    classification: s.classification,
                  }
                : f
            )
          );

          if (s.status !== "ready" && s.status !== "error") {
            allDone = false;
          }
        });

        if (allDone && Object.keys(statuses).length > 0) {
          if (pollingRef.current) clearInterval(pollingRef.current);
        }
      } catch {
        // ignore polling errors
      }
    }, 2000);
  }, []);

  // Drag & drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const droppedFiles = Array.from(e.dataTransfer.files);
      handleUpload(droppedFiles);
    },
    [handleUpload]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        handleUpload(Array.from(e.target.files));
        e.target.value = ""; // Reset so same file can be uploaded again
      }
    },
    [handleUpload]
  );

  return (
    <div className="upload-container" id="upload-container">
      <div className="upload-header">
        <h1>Upload Documents</h1>
        <p>
          Add documents to your knowledge base. Supports PDF, images, and text
          files.
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={`drop-zone ${isDragging ? "dragging" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        id="drop-zone"
      >
        <div className="icon">📁</div>
        <h3>
          Drag & drop files here, or{" "}
          <span className="browse-link">browse</span>
        </h3>
        <p>Upload multiple documents at once to the knowledge base</p>

        <div className="file-types">
          <span className="file-type-badge">PDF</span>
          <span className="file-type-badge">PNG</span>
          <span className="file-type-badge">JPG</span>
          <span className="file-type-badge">TXT</span>
          <span className="file-type-badge">TIFF</span>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.txt,.md,.csv,.tiff,.tif,.bmp"
          onChange={handleFileSelect}
          style={{ display: "none" }}
          id="file-input"
        />
      </div>

      {/* Upload progress list */}
      {files.length > 0 && (
        <div className="upload-progress-list" id="upload-progress">
          {files.map((file) => (
            <div key={file.id} className="upload-file-card">
              <div className="upload-file-icon">{getFileIcon(file.type)}</div>
              <div className="upload-file-info">
                <div className="upload-file-name">{file.name}</div>
                <div className="upload-file-size">
                  {formatFileSize(file.size)}
                  {file.classification &&
                    (file.classification as Record<string, string>)
                      .document_type && (
                      <span>
                        {" "}
                        ·{" "}
                        {
                          (file.classification as Record<string, string>)
                            .document_type
                        }
                      </span>
                    )}
                </div>
              </div>
              <div className="upload-file-status">
                {file.status !== "ready" && file.status !== "error" && (
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${STATUS_PROGRESS[file.status] || 0}%`,
                      }}
                    />
                  </div>
                )}
                <div className={`status-badge ${file.status}`}>
                  {STATUS_LABELS[file.status] || file.status}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload button for mobile */}
      {isUploading && (
        <div style={{ textAlign: "center", marginTop: 24 }}>
          <div className="animate-pulse" style={{ color: "var(--text-secondary)" }}>
            Processing documents...
          </div>
        </div>
      )}
    </div>
  );
}

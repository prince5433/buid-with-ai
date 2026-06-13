"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  sendMessage,
  getPageImageUrl,
  type ChatMessage,
  type Citation,
} from "@/lib/api";

// === Page Image Modal ===
function PageImageModal({
  documentId,
  documentName,
  pageNumber,
  onClose,
}: {
  documentId: string;
  documentName: string;
  pageNumber: number;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose} id="page-image-modal">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>{documentName}</h3>
            <span className="page-info">Page {pageNumber}</span>
          </div>
          <button className="modal-close" onClick={onClose} id="modal-close-btn">
            ✕
          </button>
        </div>
        <div className="modal-body">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={getPageImageUrl(documentId, pageNumber)}
            alt={`${documentName} - Page ${pageNumber}`}
          />
        </div>
      </div>
    </div>
  );
}

// === Citation Card ===
function CitationCard({
  citation,
  onClick,
}: {
  citation: Citation;
  onClick: () => void;
}) {
  return (
    <div className="citation-card" onClick={onClick} id={`citation-${citation.document_id}-${citation.page_number}`}>
      <div className="citation-thumbnail">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={getPageImageUrl(citation.document_id, citation.page_number)}
          alt={`${citation.document_name} page ${citation.page_number}`}
        />
      </div>
      <div className="citation-info">
        <div className="citation-doc-name">{citation.document_name}</div>
        <div className="citation-page">Page {citation.page_number}</div>
      </div>
    </div>
  );
}

// === Message Bubble ===
function MessageBubble({
  message,
  onCitationClick,
}: {
  message: ChatMessage;
  onCitationClick: (c: Citation) => void;
}) {
  return (
    <div className={`message ${message.role}`}>
      <div className="message-avatar">
        {message.role === "user" ? "👤" : "🤖"}
      </div>
      <div>
        <div className="message-content">
          {message.content.split("\n").map((line, i) => (
            <p key={i}>{line || "\u00A0"}</p>
          ))}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="citations-container">
            <div className="citations-label">📎 Sources</div>
            <div className="citations-grid">
              {message.citations.map((citation, i) => (
                <CitationCard
                  key={`${citation.document_id}-${citation.page_number}-${i}`}
                  citation={citation}
                  onClick={() => onCitationClick(citation)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// === Voice Input Hook ===
function useVoiceInput() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef<ReturnType<typeof createRecognition> | null>(null);

  useEffect(() => {
    const SpeechRecognition =
      typeof window !== "undefined"
        ? (window as unknown as Record<string, unknown>).SpeechRecognition ||
          (window as unknown as Record<string, unknown>).webkitSpeechRecognition
        : null;
    setIsSupported(!!SpeechRecognition);
  }, []);

  const startRecording = useCallback(() => {
    const SpeechRecognition =
      (window as unknown as Record<string, unknown>).SpeechRecognition ||
      (window as unknown as Record<string, unknown>).webkitSpeechRecognition;

    if (!SpeechRecognition) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const recognition = new (SpeechRecognition as any)();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      let interim = "";
      let final = "";
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript + " ";
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      setTranscript(final.trim());
      setInterimTranscript(interim);
    };

    recognition.onerror = () => {
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognition.start();
    recognitionRef.current = recognition;
    setIsRecording(true);
    setTranscript("");
    setInterimTranscript("");
  }, []);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setIsRecording(false);
    setInterimTranscript("");
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  return {
    isRecording,
    transcript,
    interimTranscript,
    isSupported,
    toggleRecording,
    fullTranscript: (transcript + " " + interimTranscript).trim(),
  };
}

function createRecognition() {
  return null;
}

// === Typing Indicator ===
function TypingIndicator() {
  return (
    <div className="message assistant">
      <div className="message-avatar">🤖</div>
      <div className="message-content">
        <div className="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  );
}

// === Main Chat Page ===
export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [modalCitation, setModalCitation] = useState<Citation | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const voice = useVoiceInput();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Fill input from voice transcript
  useEffect(() => {
    if (voice.transcript && !voice.isRecording) {
      setInput((prev) => (prev + " " + voice.transcript).trim());
    }
  }, [voice.transcript, voice.isRecording]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await sendMessage(trimmed, sessionId);
      setSessionId(response.session_id);

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.message,
        citations: response.citations,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "Sorry, I encountered an error connecting to the server. Please make sure the backend is running.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestion = (text: string) => {
    setInput(text);
    inputRef.current?.focus();
  };

  const suggestions = [
    "What documents are in the knowledge base?",
    "Summarize the financial report",
    "What are the key findings?",
    "Tell me about the meeting decisions",
  ];

  return (
    <>
      <div className="chat-container" id="chat-container">
        {/* Messages area */}
        <div className="chat-messages" id="chat-messages">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <div className="icon">🧠</div>
              <h2>DocIntel AI Assistant</h2>
              <p>
                Ask me anything about your uploaded documents. I&apos;ll answer
                with citations showing the exact source page.
              </p>
              <div className="chat-suggestions">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    className="suggestion-chip"
                    onClick={() => handleSuggestion(s)}
                    id={`suggestion-${i}`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <MessageBubble
                key={i}
                message={msg}
                onCitationClick={(c) => setModalCitation(c)}
              />
            ))
          )}

          {isLoading && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Voice transcript */}
        {voice.isRecording && voice.fullTranscript && (
          <div className="voice-transcript">
            <div className="label">🎙️ Live Transcript</div>
            <div>{voice.fullTranscript}</div>
          </div>
        )}

        {/* Input area */}
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Ask about your documents..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              id="chat-input"
            />

            {voice.isSupported && (
              <button
                className={`voice-btn ${voice.isRecording ? "recording" : ""}`}
                onClick={voice.toggleRecording}
                title={voice.isRecording ? "Stop recording" : "Start voice input"}
                id="voice-input-btn"
              >
                {voice.isRecording ? "⏹" : "🎙️"}
              </button>
            )}

            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              title="Send message"
              id="send-btn"
            >
              {isLoading ? (
                <span className="animate-spin">⟳</span>
              ) : (
                "➤"
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Page image modal */}
      {modalCitation && (
        <PageImageModal
          documentId={modalCitation.document_id}
          documentName={modalCitation.document_name}
          pageNumber={modalCitation.page_number}
          onClose={() => setModalCitation(null)}
        />
      )}
    </>
  );
}

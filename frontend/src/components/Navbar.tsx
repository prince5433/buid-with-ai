"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getStats } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const [docCount, setDocCount] = useState(0);

  useEffect(() => {
    getStats()
      .then((stats) => setDocCount(stats.documents.total))
      .catch(() => {});

    // Poll every 10s for updates
    const interval = setInterval(() => {
      getStats()
        .then((stats) => setDocCount(stats.documents.total))
        .catch(() => {});
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  return (
    <nav className="navbar" id="main-navbar">
      <Link href="/" className="navbar-brand">
        <span className="logo-icon">🧠</span>
        <span>DocIntel AI</span>
      </Link>

      <div className="navbar-links">
        <Link
          href="/"
          className={`nav-link ${pathname === "/" ? "active" : ""}`}
          id="nav-chat"
        >
          <span>💬</span>
          <span>Chat</span>
        </Link>
        <Link
          href="/upload"
          className={`nav-link ${pathname === "/upload" ? "active" : ""}`}
          id="nav-upload"
        >
          <span>📤</span>
          <span>Upload</span>
        </Link>
      </div>

      <div className="navbar-stats">
        <div className="stat-badge">
          <span>📄</span>
          <span>
            <span className="count">{docCount}</span> docs
          </span>
        </div>
      </div>
    </nav>
  );
}

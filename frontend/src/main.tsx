import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { OperatorApp } from "@/components/operator-app";
import "./globals.css";

type View = "overview" | "projects" | "evals";

function viewFromPath(pathname: string): View {
  if (pathname.startsWith("/projects")) return "projects";
  if (pathname.startsWith("/evals")) return "evals";
  return "overview";
}

function App() {
  const [view, setView] = useState<View>(() => viewFromPath(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setView(viewFromPath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  return <OperatorApp view={view} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

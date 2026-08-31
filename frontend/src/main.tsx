import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import { OperatorApp } from "@/components/operator-app";
import { ReviewerApp } from "@/components/reviewer-app";
import "./globals.css";

type View = "overview" | "settings";

function viewFromPath(pathname: string): View {
  if (pathname.startsWith("/settings")) return "settings";
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

function Root() {
  return window.location.pathname.startsWith("/review") ? <ReviewerApp /> : <App />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);

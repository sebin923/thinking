import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAiUsage } from "../api/aiUsage";

export default function useAiUsage(token) {
  const [snapshot, setSnapshot] = useState({ token: null, usage: null, error: "" });
  const revision = useRef(0);

  const apply = useCallback((usage) => {
    revision.current += 1;
    setSnapshot({ token, usage, error: "" });
  }, [token]);

  const refresh = useCallback(async () => {
    const request = ++revision.current;
    try {
      const usage = await fetchAiUsage(token);
      if (request === revision.current) setSnapshot({ token, usage, error: "" });
      return usage;
    } catch (error) {
      if (request === revision.current) {
        setSnapshot((previous) => ({ token, usage: previous.token === token ? previous.usage : null, error: error.message }));
      }
      throw error;
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const reload = () => { refresh().catch(() => {}); };
    reload();
    // Pick up top-ups from other tabs and the next day's free uses.
    window.addEventListener("focus", reload);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") reload();
    }, 60000);
    return () => {
      revision.current += 1;
      window.removeEventListener("focus", reload);
      window.clearInterval(timer);
    };
  }, [token, refresh]);

  const current = snapshot.token === token ? snapshot : { usage: null, error: "" };
  return { usage: current.usage, error: current.error, refresh, apply };
}

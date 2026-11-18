import { useCallback, useEffect, useRef, useState } from "react";
import { createPageHistory, readPage } from "../utils/pageHistory";

export default function usePageNavigation(initialPage) {
  const [route, setRoute] = useState(() => ({
    page: initialPage || readPage(window.location), data: null,
  }));
  const callbacks = useRef({});
  const navigation = useRef(null);

  useEffect(() => {
    navigation.current = createPageHistory(window, {
      initialPage,
      onChange: setRoute,
      shouldBlock: (...args) => callbacks.current.shouldBlock?.(...args) ?? false,
      onBlocked: (retry) => callbacks.current.onBlocked?.(retry),
      onTraverse: (...args) => callbacks.current.onTraverse?.(...args),
    });
    return () => navigation.current.destroy();
  }, [initialPage]);

  const navigate = useCallback((page, options) => navigation.current.navigate(page, options), []);
  const back = useCallback((fallback, data) => navigation.current.back(fallback, data), []);
  const setHandlers = useCallback((handlers) => { callbacks.current = handlers; }, []);
  return [route, navigate, back, setHandlers];
}

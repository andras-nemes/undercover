import { useEffect, useState } from "react";
import { getJson } from "./api";

const REFRESH_MS = 2000;

// keepFresh must not change between renders, so define it at module level.
export function useApi<T>(
  path: string,
  keepFresh: (data: T) => boolean = () => false,
): { data: T | null; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [round, setRound] = useState(0);

  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    getJson<T>(path)
      .then((value) => {
        if (!live) return;
        setData(value);
        setError(null);
        if (keepFresh(value)) {
          timer = window.setTimeout(() => {
            setRound((n) => n + 1);
          }, REFRESH_MS);
        }
      })
      .catch((failure: unknown) => {
        if (live) setError(String(failure));
      });
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [path, round, keepFresh]);

  return {
    data,
    error,
    reload: () => {
      setRound((n) => n + 1);
    },
  };
}

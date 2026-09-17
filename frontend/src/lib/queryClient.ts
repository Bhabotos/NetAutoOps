import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (failureCount, error) => {
        // 401 is handled globally (redirect to login); 403/404 are
        // permanent for the current user/resource -- retrying wastes a
        // round trip and delays the error state from appearing.
        if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
          return false;
        }
        return failureCount < 2;
      },
    },
  },
});

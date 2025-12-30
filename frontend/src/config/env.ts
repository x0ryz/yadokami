export const config = {
  apiUrl: "/api",

  wsUrl:
    window.location.protocol === "https:"
      ? `wss://${window.location.host}/ws/messages`
      : `ws://${window.location.host}/ws/messages`,

  wsToken: import.meta.env.VITE_WS_TOKEN,
} as const;

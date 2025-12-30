import { useEffect, useState } from "react";
import { EventType, EventHandler, wsService } from "./websocket";

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(wsService.isConnected());

  useEffect(() => {
    // Підключаємося, якщо ще не підключені
    wsService.connect();

    // Підписуємося на зміни статусу з'єднання
    // (Потрібно додати метод onConnectionChange у ваш клас WebSocketService, 
    // або використовувати setInterval як у вас було, але краще через callback)
    const unsubscribe = wsService.onConnectionChange((status) => {
      setIsConnected(status);
    });

    return () => {
      // НЕ викликаємо wsService.disconnect() тут!
      // Просто відписуємося від оновлень статусу
      unsubscribe();
    };
  }, []);

  return { isConnected };
}

export function useWSEvent(
  eventType: EventType,
  handler: EventHandler
) {
  useEffect(() => {
    // Огортаємо handler, щоб уникнути проблем, якщо він не мемоізований
    const safeHandler = (data: any) => handler(data);
    
    wsService.on(eventType, safeHandler);
    
    return () => {
      wsService.off(eventType, safeHandler);
    };
  }, [eventType, handler]); // Важливо: handler має бути обгорнутий в useCallback у компоненті, або useWSEvent має сам це обробляти
}
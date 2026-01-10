import { useLocation, useSearchParams } from "react-router-dom";
import toast, { Toaster } from "react-hot-toast";
import { useWSEvent } from "../services/useWebSocket";
import { EventType } from "../services/websocket";

export const NotificationManager = () => {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // 1. Повідомлення
  useWSEvent(EventType.NEW_MESSAGE, (data) => {
    const activeContactId =
      searchParams.get("id") || searchParams.get("contact_id");
    if (
      location.pathname.includes("/contacts") &&
      activeContactId === data.contact_id
    )
      return;

    toast.success(
      <div>
        <p className="font-bold text-sm">Нове повідомлення</p>
        <p className="text-xs text-gray-600">{data.phone}</p>
        <p className="text-sm mt-1 truncate">{data.body}</p>
      </div>,
      { duration: 4000 },
    );
  });

  // 2. Шаблони (дані прийшли з вебхука: name, status)
  useWSEvent(EventType.TEMPLATE_STATUS_UPDATE, (data) => {
    const isApproved = data.status === "APPROVED";
    const isRejected = data.status === "REJECTED";

    toast(
      <div>
        <p className="font-bold text-sm">Шаблон: {data.name}</p>
        <p
          className={`text-sm mt-1 ${isApproved ? "text-green-600" : isRejected ? "text-red-600" : "text-yellow-600"}`}
        >
          Статус: {data.status}
        </p>
        {data.reason && (
          <p className="text-xs text-gray-500 mt-1">{data.reason}</p>
        )}
      </div>,
      { icon: isApproved ? "✅" : isRejected ? "❌" : "⚠️", duration: 5000 },
    );
  });

  // 3. Якість номеру
  useWSEvent(EventType.PHONE_STATUS_UPDATE, (data) => {
    const isBad = data.event === "FLAGGED" || data.event === "DOWNGRADE";

    toast(
      <div>
        <p className="font-bold text-sm">Номер: {data.display_phone_number}</p>
        <p className="text-xs mt-1">Подія: {data.event}</p>
        <p className="text-xs">Ліміт: {data.messaging_limit_tier}</p>
      </div>,
      { icon: isBad ? "📉" : "📈", duration: 5000 },
    );
  });

  // 4. Акаунт
  useWSEvent(EventType.WABA_STATUS_UPDATE, (data) => {
    toast(
      <div>
        <p className="font-bold text-sm">WABA Акаунт</p>
        <p className="text-sm">Новий статус: {data.status}</p>
      </div>,
      { icon: "🏢" },
    );
  });

  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        className: "bg-white shadow-lg border border-gray-100",
        style: { padding: "16px", color: "#333" },
      }}
    />
  );
};

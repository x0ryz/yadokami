import React from "react";
import { Link, useLocation } from "react-router-dom";
import { LayoutDashboard, Users, FileText, Send } from "lucide-react";

const Navigation: React.FC = () => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path
      ? "bg-blue-600 text-white"
      : "text-gray-700 hover:bg-gray-100";
  };

  return (
    <nav className="bg-white shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-1">
            <h1 className="text-xl font-bold text-gray-800">Golden Cars CRM</h1>
          </div>
          <div className="flex space-x-1">
            <Link
              to="/dashboard"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive(
                "/dashboard",
              )}`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Головна
            </Link>
            <Link
              to="/contacts"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive(
                "/contacts",
              )}`}
            >
              <Users className="w-4 h-4" />
              Контакти
            </Link>
            <Link
              to="/templates"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive(
                "/templates",
              )}`}
            >
              <FileText className="w-4 h-4" />
              Шаблони
            </Link>
            <Link
              to="/campaigns"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive(
                "/campaigns",
              )}`}
            >
              <Send className="w-4 h-4" />
              Розсилки
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;

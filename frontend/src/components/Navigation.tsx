import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Navigation: React.FC = () => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path
      ? 'bg-blue-600 text-white'
      : 'text-gray-700 hover:bg-gray-100';
  };

  return (
    <nav className="bg-white shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-1">
            <h1 className="text-xl font-bold text-gray-800">Jidoka</h1>
          </div>
          <div className="flex space-x-1">
            <Link
              to="/contacts"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${isActive(
                '/contacts'
              )}`}
            >
              Контакти
            </Link>
            <Link
              to="/templates"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${isActive(
                '/templates'
              )}`}
            >
              Шаблони
            </Link>
            <Link
              to="/campaigns"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${isActive(
                '/campaigns'
              )}`}
            >
              Розсилки
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;





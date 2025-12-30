import React from 'react';
import Navigation from './Navigation';
import { useWebSocket } from '../services/useWebSocket';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isConnected } = useWebSocket();

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      {!isConnected && (
        <div className="bg-red-500 text-white text-xs p-1 text-center">
          Відключено. Спроба з'єднання...
        </div>
      )}
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
};

export default Layout;





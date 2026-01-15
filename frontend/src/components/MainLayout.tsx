'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { useSidebar } from '@/components/Sidebar/SidebarProvider';

export default function MainLayout({ children }: { children: React.ReactNode }) {
    const { isCollapsed } = useSidebar();

    return (
        <>
            <Sidebar />
            <div
                className={`min-h-screen bg-gray-50 transition-all duration-300 ${isCollapsed ? 'ml-16' : 'ml-64'
                    }`}
            >
                {children}
            </div>
        </>
    );
}

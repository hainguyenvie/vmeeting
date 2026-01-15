'use client'

import './globals.css'
import { Source_Sans_3 } from 'next/font/google'
import { Toaster } from 'sonner'
import "sonner/dist/styles.css"
import { SidebarProvider } from '@/components/Sidebar/SidebarProvider'
import MainLayout from '@/components/MainLayout'

const sourceSans3 = Source_Sans_3({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-source-sans-3',
})

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${sourceSans3.variable} font-sans bg-gray-50`}>
        <SidebarProvider>
          <MainLayout>
            {children}
          </MainLayout>
          <Toaster position="bottom-center" richColors closeButton />
        </SidebarProvider>
      </body>
    </html>
  )
}

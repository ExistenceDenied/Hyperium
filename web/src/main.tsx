import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './components/Layout'
import { PeriodProvider } from './state/period'
import { SettingsProvider } from './state/settings'
import { ToastProvider } from './components/ui'
import Dashboard from './pages/Dashboard'
import CalendarPage from './pages/Calendar'
import Timesheet from './pages/Timesheet'
import Invoices from './pages/Invoices'
import Expenses from './pages/Expenses'
import Archive from './pages/Archive'
import Settings from './pages/Settings'
import './index.css'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'calendar', element: <CalendarPage /> },
      { path: 'timesheet', element: <Timesheet /> },
      { path: 'invoices', element: <Invoices /> },
      { path: 'expenses', element: <Expenses /> },
      { path: 'archive', element: <Archive /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
], {
  future: { v7_relativeSplatPath: true },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ToastProvider>
      <SettingsProvider>
        <PeriodProvider>
          <RouterProvider router={router} future={{ v7_startTransition: true }} />
        </PeriodProvider>
      </SettingsProvider>
    </ToastProvider>
  </React.StrictMode>,
)

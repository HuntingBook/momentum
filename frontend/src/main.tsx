import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { ToastProvider } from './components/Toast'
import ErrorBoundary from './components/ErrorBoundary'
import './index.css'
import 'react-day-picker/dist/style.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <ErrorBoundary>
            <ToastProvider>
                <BrowserRouter>
                    <App />
                </BrowserRouter>
            </ToastProvider>
        </ErrorBoundary>
    </React.StrictMode>,
)

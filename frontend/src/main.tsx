import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './Layout'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Chat from './pages/Chat'
import Article from './pages/Article'
import Monitor from './pages/Monitor'
import './app/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/search" element={<Search />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/article" element={<Article />} />
        <Route path="/monitor" element={<Monitor />} />
      </Route>
    </Routes>
  </BrowserRouter>
)

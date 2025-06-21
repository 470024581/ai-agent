import { Routes, Route, Navigate } from 'react-router-dom'
import Header from './components/Header'
import QueryForm from './components/QueryForm'
import DataSourceManager from './components/DataSourceManager'
import IntelligentAnalysis from './components/IntelligentAnalysis'

function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50/50 via-pink-50/50 to-purple-50/50 font-sans antialiased">
      <Header />
      <main className="container mx-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate replace to="/query" />} />
          <Route path="/query" element={<QueryForm />} />
          <Route path="/intelligent-analysis" element={<IntelligentAnalysis />} />
          <Route path="/datasources" element={<DataSourceManager />} />
        </Routes>
      </main>
    </div>
  )
}

export default App 
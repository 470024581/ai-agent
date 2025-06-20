import { Routes, Route, Navigate } from 'react-router-dom'
import { Container } from 'react-bootstrap'
import Header from './components/Header'
import QueryForm from './components/QueryForm'
import DataSourceManager from './components/DataSourceManager'

function App() {
  return (
    <>
      <Header />
      <Container fluid className="py-4">
        <Routes>
          <Route path="/" element={<Navigate replace to="/query" />} />
          <Route path="/query" element={<QueryForm />} />
          <Route path="/datasources" element={<DataSourceManager />} />
        </Routes>
      </Container>
    </>
  )
}

export default App 